# stasiun-cuaca
with esp32 s3 super mini



import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, session, redirect, url_for, flash, jsonify
from flask_socketio import SocketIO
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, db
import pymysql
import time

# Import konfigurasi dan routes
from config import init_mysql
from routes.auth import init_auth_routes
from routes.export import init_export_routes
from routes.sensor_api import init_sensor_routes

app = Flask(__name__)
app.secret_key = 'pQhilHgCRQmetKWruJagH4VrArxh18JpeWFzEToK'
CORS(app)

socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# Firebase setup
cred = credentials.Certificate("D:\stasiun-cuaca-main2\stasiun-cuaca-firebase-b2220-firebase-adminsdk-fbsvc-cb0a86f39d.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://stasiun-cuaca-firebase-b2220-default-rtdb.firebaseio.com/'
})
firebase_ref = db.reference("tb_bme280")

# MySQL setup
mysql = init_mysql(app)
mysql_online = True
last_mysql_down = None

# === Utility ===

def is_mysql_alive():
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        return True
    except:
        return False

def should_use_firebase_only():
    return not mysql_online or (last_mysql_down and (datetime.now() - last_mysql_down).total_seconds() < 120)

def send_to_firebase(data):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    firebase_ref.push({**data, "waktu": timestamp})

def send_data(data):
    global mysql_online, last_mysql_down

    if should_use_firebase_only():
        send_to_firebase(data)
    else:
        try:
            cursor = mysql.connection.cursor()
            sql = """INSERT INTO tb_bme280 (suhu, kelembapan, tekanan, altitude, status_udara, kebakaran, jarak, waktu)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
            values = (
                data['suhu'], data['kelembapan'], data['tekanan'],
                data['altitude'], data['status_udara'],
                data['kebakaran'], data['jarak'],
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
            cursor.execute(sql, values)
            mysql.connection.commit()
            cursor.close()

            send_to_firebase(data)
        except Exception as e:
            print("Gagal kirim ke MySQL, fallback ke Firebase:", e)
            mysql_online = False
            last_mysql_down = datetime.now()
            send_to_firebase(data)

def mysql_health_check():
    global mysql_online, last_mysql_down

    if last_mysql_down and (datetime.now() - last_mysql_down).total_seconds() < 120:
        return

    start_time = time.time()
    while time.time() - start_time < 5:
        if is_mysql_alive():
            if not mysql_online:
                print("✅ MySQL kembali online.")
            mysql_online = True
            last_mysql_down = None
            return
        time.sleep(1)

    if mysql_online:
        print("❌ MySQL masih mati.")
    mysql_online = False
    last_mysql_down = datetime.now()

def delete_old_data():
    global mysql_online, last_mysql_down
    time_threshold = datetime.now() - timedelta(hours=2)

    deleted_mysql = 0
    if mysql_online:
        try:
            cursor = mysql.connection.cursor()
            cursor.execute("DELETE FROM tb_bme280 WHERE waktu < %s", (time_threshold,))
            deleted_mysql = cursor.rowcount
            mysql.connection.commit()
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

# === Halaman Utama ===

@app.route('/')
def index():
    if 'loggedin' in session:
        latest_data = []

        if should_use_firebase_only():
            firebase_data = firebase_ref.get()
            if firebase_data:
                latest_data = sorted(
                    [v for v in firebase_data.values()],
                    key=lambda x: x.get('waktu', ''),
                    reverse=True
                )[:10]
        else:
            try:
                cursor = mysql.connection.cursor(pymysql.cursors.DictCursor)
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

# === Blueprint ===

init_auth_routes(app, mysql)
init_export_routes(app, mysql)
init_sensor_routes(app, mysql, socketio, firebase_ref, should_use_firebase_only, lambda: None, send_data)

# === Scheduler ===

scheduler = BackgroundScheduler()
scheduler.add_job(delete_old_data, 'interval', minutes=1)
scheduler.add_job(mysql_health_check, 'interval', minutes=2)
scheduler.start()

# === Run App ===

if __name__ == '__main__':
    print("[INFO] Flask backend is running...")
    socketio.run(app, host='127.0.0.1', port=5002, debug=True)
