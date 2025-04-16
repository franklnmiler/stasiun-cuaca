from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint('auth', __name__)

def init_auth_routes(app, mysql):
    @auth_bp.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            email = request.form['email']
            password = request.form['password']
            cursor = mysql.connection.cursor()
            cursor.execute('SELECT username, password FROM tb_users WHERE email=%s', (email,))
            akun = cursor.fetchone()

            if not akun:
                flash('Login gagal, email tidak ditemukan', 'danger')
            elif not check_password_hash(akun[1], password):
                flash('Login gagal, cek password anda', 'danger')
            else:
                session['loggedin'] = True
                session['username'] = akun[0]
                return redirect(url_for('index'))
        return render_template('login.html')

    @auth_bp.route('/registrasi', methods=['GET', 'POST'])
    def registrasi():
        if request.method == 'POST':
            username = request.form['username']
            email = request.form['email']
            password = request.form['password']

            cursor = mysql.connection.cursor()
            cursor.execute('SELECT * FROM tb_users WHERE username=%s OR email=%s', (username, email))
            akun = cursor.fetchone()

            if not akun:
                cursor.execute("INSERT INTO tb_users (username, email, password) VALUES (%s, %s, %s)", 
                            (username, email, generate_password_hash(password)))
                mysql.connection.commit()
                flash('Registrasi berhasil! Silakan login.', 'success')
                return redirect(url_for('auth.login'))
            else:
                flash('Username atau email sudah digunakan', 'danger')
        return render_template('registrasi.html')

    @auth_bp.route('/logout')
    def logout():
        session.pop('loggedin', None)
        session.pop('username', None)
        return redirect(url_for('auth.login'))

    app.register_blueprint(auth_bp)
