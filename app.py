import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, session, redirect, url_for, flash
from flask_socketio import SocketIO
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

# Import konfigurasi dan routes
from config import init_mysql
from routes.auth import init_auth_routes
from routes.export import init_export_routes
from routes.sensor_api import init_sensor_routes

# Inisialisasi Flask app
app = Flask(__name__)
app.secret_key = 'bebasapasaja'
CORS(app)

# Inisialisasi SocketIO
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# Inisialisasi koneksi database MySQL
mysql = init_mysql(app)

# Fungsi hapus data lama (lebih dari 2 jam)
def delete_old_data():
    with app.app_context():
        time_threshold = datetime.now() - timedelta(hours=2)
        cursor = mysql.connection.cursor()

        # Hitung jumlah data yang akan dihapus
        cursor.execute("SELECT COUNT(*) FROM tb_bme280 WHERE waktu < %s", (time_threshold,))
        count = cursor.fetchone()[0]

        # Hapus data jika ada
        if count > 0:
            cursor.execute("DELETE FROM tb_bme280 WHERE waktu < %s", (time_threshold,))
            mysql.connection.commit()

        cursor.close()

        # Log ke terminal dan kirim ke browser
        log_message = f"[{datetime.now()}] {count} data lebih dari 2 jam dihapus."
        print(log_message)
        socketio.emit('data_deleted', {
            'count': count,
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

# Scheduler untuk hapus data setiap 1 menit
scheduler = BackgroundScheduler()
scheduler.add_job(delete_old_data, 'interval', minutes=1)
scheduler.start()

# Rute utama
@app.route('/')
def index():
    if 'loggedin' in session:
        time_threshold = datetime.now() - timedelta(hours=2)
        cursor = mysql.connection.cursor()
        cursor.execute(
            "SELECT * FROM tb_bme280 WHERE waktu >= %s ORDER BY waktu DESC LIMIT 10",
            (time_threshold,)
        )
        data = cursor.fetchall()
        cursor.close()
        return render_template('index.html', data=data)
    flash('Silakan login terlebih dahulu', 'danger')
    return redirect(url_for('auth.login'))

# Inisialisasi semua blueprint
init_auth_routes(app, mysql)
init_export_routes(app, mysql)
init_sensor_routes(app, mysql, socketio)

# Event SocketIO
@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

# Jalankan server Flask
if __name__ == '__main__':
    socketio.run(app, host='kelompok7.com', port=5002, debug=True)
