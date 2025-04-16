from flask import Blueprint, Response
from io import StringIO
import csv

export_bp = Blueprint('export', __name__)

def init_export_routes(app, mysql):
    @export_bp.route('/export/csv')
    def export_csv():
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT suhu, kelembapan, tekanan, altitude, mq135_ppm, waktu FROM tb_bme280 ORDER BY waktu DESC")
        data = cursor.fetchall()
        cursor.close()

        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(['Suhu', 'Kelembapan', 'Tekanan', 'Altitude', 'MQ135 (ppm)', 'Waktu'])
        for row in data:
            cw.writerow(row)

        return Response(si.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment;filename=data_sensor.csv"})

    app.register_blueprint(export_bp)
