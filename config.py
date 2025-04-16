from flask_mysqldb import MySQL

def init_mysql(app):
    app.config['MYSQL_HOST'] = 'kelompok7.com'
    app.config['MYSQL_USER'] = 'irsyad'
    app.config['MYSQL_PASSWORD'] = '312310512'
    app.config['MYSQL_DB'] = 'kelompok7'
    return MySQL(app)
