from flask import Blueprint, request, jsonify
from datetime import datetime
from flask_socketio import emit
from utils import get_air_quality_status  # Pastikan fungsi ini ada
import logging

sensor_bp = Blueprint('sensor', __name__)
logging.basicConfig(level=logging.INFO)

def init_sensor_routes(app, mysql, socketio):
    # =====================================
    # API POST DATA BME280 + MQ135 + Ultrasonik
    # =====================================
    @sensor_bp.route('/api/bme280/post', methods=['POST'])
    def post_bme280_data():
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400

        try:
            data = request.get_json()

            # Data utama sensor
            suhu = data.get('suhu')
            kelembapan = data.get('kelembapan')
            tekanan = data.get('tekanan')
            altitude = data.get('altitude')
            mq135_ppm = data.get('mq135_ppm')
            jarak_ultrasonik = data.get('jarak_ultrasonik')  # data baru

            # Validasi nilai "inf"
            if mq135_ppm == "inf":
                mq135_ppm = None

            # Data lokasi opsional
            lokasi = data.get('lokasi')
            latitude = data.get('latitude')
            longitude = data.get('longitude')

            # Validasi data wajib
            if None in [suhu, kelembapan, tekanan, altitude, mq135_ppm]:
                return jsonify({"error": "Data tidak lengkap"}), 400

            status_udara = get_air_quality_status(mq135_ppm)
            waktu = datetime.now()

            # Simpan ke database
            with mysql.connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO tb_bme280 
                    (suhu, kelembapan, tekanan, altitude, mq135_ppm, jarak_ultrasonik, waktu, status_udara, lokasi, latitude, longitude)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    suhu, kelembapan, tekanan, altitude, mq135_ppm, jarak_ultrasonik,
                    waktu, status_udara, lokasi, latitude, longitude
                ))
                mysql.connection.commit()

            # Kirim ke WebSocket
            socketio.emit('new_data', {
                'suhu': suhu,
                'kelembapan': kelembapan,
                'tekanan': tekanan,
                'altitude': altitude,
                'mq135_ppm': mq135_ppm,
                'jarak_ultrasonik': jarak_ultrasonik,
                'status_udara': status_udara,
                'waktu': waktu.strftime('%H:%M:%S'),
                'lokasi': lokasi,
                'latitude': latitude,
                'longitude': longitude
            })

            return jsonify({"message": "Data berhasil disimpan!"}), 201

        except Exception as e:
            logging.error(f"Error: {str(e)}")
            return jsonify({"error": str(e)}), 400

    # =====================================
    # API CHART SUHU SAJA
    # =====================================
    @sensor_bp.route('/api/bme280/chart')
    def chart_data():
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT waktu, suhu FROM tb_bme280 ORDER BY waktu DESC LIMIT 10")
        results = cursor.fetchall()
        cursor.close()

        waktu = [row[0].strftime('%H:%M:%S') for row in results][::-1]
        suhu = [row[1] for row in results][::-1]

        return jsonify({"labels": waktu, "data": suhu})

    # =====================================
    # API CHART SEMUA PARAMETER
    # =====================================
    @sensor_bp.route('/api/bme280/chart-multi')
    def chart_data_multi():
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT waktu, suhu, kelembapan, tekanan, altitude, mq135_ppm, jarak_ultrasonik
            FROM tb_bme280 
            WHERE waktu >= NOW() - INTERVAL 10 MINUTE 
            ORDER BY waktu ASC
        """)
        results = cursor.fetchall()
        cursor.close()

        waktu = [row[0].strftime('%H:%M:%S') for row in results]
        suhu = [row[1] for row in results]
        kelembapan = [row[2] for row in results]
        tekanan = [row[3] for row in results]
        altitude = [row[4] for row in results]
        mq135_ppm = [row[5] for row in results]
        jarak_ultrasonik = [row[6] for row in results]

        return jsonify({
            "labels": waktu,
            "suhu": suhu,
            "kelembapan": kelembapan,
            "tekanan": tekanan,
            "altitude": altitude,
            "mq135_ppm": mq135_ppm,
            "jarak_ultrasonik": jarak_ultrasonik
        })

    # =====================================
    # REGISTER BLUEPRINT
    # =====================================
    app.register_blueprint(sensor_bp)
