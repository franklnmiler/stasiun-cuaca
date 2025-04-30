import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify, Blueprint
from flask_socketio import SocketIO
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, db
import pymysql
import time
import logging

from utils import get_air_quality_status
from routes.auth import init_auth_routes
from config import init_firebase, init_mysql
from extensions import mysql as ext_mysql, firebase_ref as ext_firebase_ref, socketio as ext_socketio, send_data as ext_send_data



# === Flask App Setup ===
app = Flask(__name__)
app.secret_key = 'your-secret-key'
CORS(app)
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# === Firebase Setup ===
firebase_ref = init_firebase()
mysql = init_mysql(app)

# === Auth Blueprint Registration ===
init_auth_routes(app, mysql)

# === Logging Setup ===
logging.basicConfig(level=logging.INFO)

# === Global State ===
mysql_online = True
last_mysql_down = None

# === Utility Functions ===
def is_mysql_alive():
    try:
        cursor = mysql.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        return True
    except:
        return False

def should_use_firebase_only():
    global mysql_online, last_mysql_down
    return not mysql_online or (last_mysql_down and (datetime.now() - last_mysql_down).total_seconds() < 120)

def send_to_firebase(data):
    firebase_ref.push({**data, "waktu": datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

def send_data(data):
    global mysql_online, last_mysql_down
    if should_use_firebase_only():
        send_to_firebase(data)
        return

    try:
        cursor = mysql.cursor()
        sql = """
            INSERT INTO tb_bme280 (suhu, kelembapan, tekanan, altitude, status_udara, kebakaran, jarak_ultrasonik, waktu)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            data['suhu'], data['kelembapan'], data['tekanan'], data['altitude'],
            data['status_udara'], data['kebakaran'], data['jarak_ultrasonik'],
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        cursor.execute(sql, values)
        mysql.commit()
        cursor.close()
        send_to_firebase(data)
    except Exception as e:
        print(f"❌ Gagal simpan ke MySQL, fallback Firebase: {e}")
        mysql_online = False
        last_mysql_down = datetime.now()
        send_to_firebase(data)

def mysql_health_check():
    global mysql_online, last_mysql_down
    if last_mysql_down and (datetime.now() - last_mysql_down).total_seconds() < 120:
        return
    try:
        if is_mysql_alive():
            mysql_online = True
            last_mysql_down = None
            print("✅ MySQL kembali online.")
        else:
            raise Exception("Timeout")
    except:
        mysql_online = False
        last_mysql_down = datetime.now()
        print("❌ MySQL masih mati.")

def delete_old_data():
    global mysql_online, last_mysql_down
    time_threshold = datetime.now() - timedelta(hours=2)

    deleted_mysql = 0
    if mysql_online:
        try:
            cursor = mysql.cursor()
            cursor.execute("DELETE FROM tb_bme280 WHERE waktu < %s", (time_threshold,))
            deleted_mysql = cursor.rowcount
            mysql.commit()
            cursor.close()
        except:
            mysql_online = False
            last_mysql_down = datetime.now()

    firebase_data = firebase_ref.get()
    deleted_firebase = 0
    if firebase_data:
        for key, entry in firebase_data.items():
            try:
                waktu = datetime.strptime(entry.get('waktu'), '%Y-%m-%d %H:%M:%S')
                if waktu < time_threshold:
                    firebase_ref.child(key).delete()
                    deleted_firebase += 1
            except:
                continue

    print(f"[{datetime.now()}] Hapus MySQL: {deleted_mysql}, Firebase: {deleted_firebase}")
    socketio.emit('data_deleted', {
        'mysql': deleted_mysql,
        'firebase': deleted_firebase,
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

# === Routes ===
@app.route('/')
def index():
    if 'loggedin' in session:
        latest_data = []
        if should_use_firebase_only():
            firebase_data = firebase_ref.get()
            if firebase_data:
                latest_data = sorted(firebase_data.values(), key=lambda x: x.get('waktu', ''), reverse=True)[:10]
        else:
            try:
                cursor = mysql.cursor(pymysql.cursors.DictCursor)
                cursor.execute("SELECT * FROM tb_bme280 ORDER BY waktu DESC LIMIT 10")
                latest_data = cursor.fetchall()
                cursor.close()
            except:
                mysql_online = False
                last_mysql_down = datetime.now()
        return render_template('index.html', data=latest_data)
    flash('Silakan login terlebih dahulu', 'danger')
    return redirect(url_for('auth.login'))

# === WebSocket Events ===
@socketio.on('connect')
def handle_connect():
    print('[WebSocket] Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('[WebSocket] Client disconnected')

# === Sensor API Blueprint ===
sensor_bp = Blueprint('sensor', __name__)

@sensor_bp.route('/api/bme280/post', methods=['POST'])
def post_bme280_data():
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400
    try:
        data = request.get_json()
        suhu = data.get('suhu')
        kelembapan = data.get('kelembapan')
        tekanan = data.get('tekanan')
        altitude = data.get('altitude')
        mq135_ppm = data.get('mq135_ppm')
        jarak = data.get('jarak_ultrasonik')
        lokasi = data.get('lokasi')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        kebakaran = data.get('kebakaran', None)

        if mq135_ppm == "inf":
            mq135_ppm = None

        if None in [suhu, kelembapan, tekanan, altitude, mq135_ppm, jarak]:
            return jsonify({"error": "Data tidak lengkap"}), 400

        status_udara = get_air_quality_status(mq135_ppm)
        waktu = datetime.now()

        sensor_data = {
            "suhu": suhu,
            "kelembapan": kelembapan,
            "tekanan": tekanan,
            "altitude": altitude,
            "mq135_ppm": mq135_ppm,
            "jarak_ultrasonik": jarak,
            "status_udara": status_udara,
            "lokasi": lokasi,
            "latitude": latitude,
            "longitude": longitude,
            "kebakaran": kebakaran
        }

        send_data(sensor_data)
        socketio.emit('new_data', {**sensor_data, "waktu": waktu.strftime('%H:%M:%S')})
        return jsonify({"message": "Data berhasil disimpan!"}), 201

    except Exception as e:
        logging.error(f"Error saat menyimpan data sensor: {str(e)}")
        return jsonify({"error": str(e)}), 500

@sensor_bp.route('/api/bme280/chart-multi', methods=['GET'])
def get_chart_data():
    try:
        cursor = mysql.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT waktu, suhu, kelembapan, tekanan FROM tb_bme280 ORDER BY waktu DESC LIMIT 20")
        rows = cursor.fetchall()
        cursor.close()

        rows = sorted(rows, key=lambda x: x['waktu'])  # urutkan naik
        labels = [row['waktu'].strftime('%H:%M:%S') for row in rows]
        suhu = [row['suhu'] for row in rows]
        kelembapan = [row['kelembapan'] for row in rows]
        tekanan = [row['tekanan'] for row in rows]

        return jsonify({
            'labels': labels,
            'suhu': suhu,
            'kelembapan': kelembapan,
            'tekanan': tekanan
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

app.register_blueprint(sensor_bp)

# === Scheduler ===
scheduler = BackgroundScheduler()
scheduler.add_job(delete_old_data, 'interval', minutes=1)
scheduler.add_job(mysql_health_check, 'interval', minutes=2)
scheduler.start()

# === Run Server ===
if __name__ == '__main__':
    print("[INFO] Flask backend is running...")
    socketio.run(app, host='192.168.1.3', port=5002, debug=True)
