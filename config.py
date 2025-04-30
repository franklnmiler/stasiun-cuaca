# config.py
import firebase_admin
from firebase_admin import credentials, db
import pymysql

from flask import current_app

# === Firebase Setup ===
def init_firebase():
    cred = credentials.Certificate("stasiun-cuaca-firebase-b2220-firebase-adminsdk-fbsvc-cb0a86f39d.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://stasiun-cuaca-firebase-b2220-default-rtdb.firebaseio.com/'
    })
    return db.reference("tb_bme280")

# === MySQL Setup ===
def init_mysql(app):
    app.config['MYSQL_HOST'] = '192.168.1.3'
    app.config['MYSQL_USER'] = 'irsyad'
    app.config['MYSQL_PASSWORD'] = '312310512'
    app.config['MYSQL_DB'] = 'kelompok7'

    connection = pymysql.connect(
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        database=app.config['MYSQL_DB']
    )
    return connection
