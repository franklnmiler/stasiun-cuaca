from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from flask_socketio import emit
from utils import get_air_quality_status
import logging

sensor_bp = Blueprint('sensor', __name__)
logging.basicConfig(level=logging.INFO)

def init_sensor_routes(app, mysql, socketio, firebase_ref, should_use_firebase_only, mirror_mysql_to_firebase, send_data):
    # =====================================
    # POST DATA SENSOR
    # =====================================
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
                "jarak": jarak,
                "status_udara": status_udara,
                "lokasi": lokasi,
                "latitude": latitude,
                "longitude": longitude
            }

            send_data(sensor_data)

            socketio.emit('new_data', {
                **sensor_data,
                "waktu": waktu.strftime('%H:%M:%S')
            })

            return jsonify({"message": "Data berhasil disimpan!"}), 201

        except Exception as e:
            logging.error(f"Error saat menyimpan data sensor: {str(e)}")
            return jsonify({"error": str(e)}), 500

    # =====================================
    # API CHART SUHU SAJA
    # =====================================
    @sensor_bp.route('/api/bme280/chart')
    def chart_data():
        try:
            if should_use_firebase_only():
                data = firebase_ref.order_by_child("waktu").limit_to_last(10).get()
                if not data:
                    return jsonify({"labels": [], "data": []})
                data_sorted = sorted(data.values(), key=lambda x: x.get("waktu", ""))[-10:]
                waktu = [datetime.strptime(d["waktu"], "%Y-%m-%d %H:%M:%S").strftime('%H:%M:%S') for d in data_sorted]
                suhu = [d["suhu"] for d in data_sorted]
            else:
                cursor = mysql.connection.cursor()
                cursor.execute("SELECT waktu, suhu FROM tb_bme280 ORDER BY waktu DESC LIMIT 10")
                results = cursor.fetchall()
                cursor.close()
                waktu = [row[0].strftime('%H:%M:%S') for row in results][::-1]
                suhu = [row[1] for row in results][::-1]

            return jsonify({"labels": waktu, "data": suhu})
        except Exception as e:
            logging.error(f"Error saat mengambil data chart suhu: {str(e)}")
            return jsonify({"error": "Terjadi kesalahan saat mengambil data chart suhu"}), 500

    # =====================================
    # API CHART MULTI PARAMETER
    # =====================================
    @sensor_bp.route('/api/bme280/chart-multi')
    def chart_data_multi():
        try:
            if should_use_firebase_only():
                data = firebase_ref.order_by_child("waktu").get()
                if not data:
                    return jsonify({})
                data_sorted = sorted(data.values(), key=lambda x: x.get("waktu", ""))
                data_filtered = [
                    d for d in data_sorted
                    if datetime.strptime(d["waktu"], "%Y-%m-%d %H:%M:%S") >= datetime.now() - timedelta(minutes=10)
                ]
                waktu = [datetime.strptime(d["waktu"], "%Y-%m-%d %H:%M:%S").strftime('%H:%M:%S') for d in data_filtered]
                suhu = [d["suhu"] for d in data_filtered]
                kelembapan = [d["kelembapan"] for d in data_filtered]
                tekanan = [d["tekanan"] for d in data_filtered]
                altitude = [d["altitude"] for d in data_filtered]
                mq135_ppm = [d["mq135_ppm"] for d in data_filtered]
                jarak = [d["jarak"] for d in data_filtered]
            else:
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
                jarak = [row[6] for row in results]

            return jsonify({
                "labels": waktu,
                "suhu": suhu,
                "kelembapan": kelembapan,
                "tekanan": tekanan,
                "altitude": altitude,
                "mq135_ppm": mq135_ppm,
                "jarak_ultrasonik": jarak
            })
        except Exception as e:
            logging.error(f"Error saat mengambil data chart multi parameter: {str(e)}")
            return jsonify({"error": "Terjadi kesalahan saat mengambil data chart multi parameter"}), 500
