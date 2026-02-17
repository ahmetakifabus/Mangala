from flask import Flask, request, jsonify, send_file
import sqlite3
import os
import random
import smtplib
from email.mime.text import MIMEText
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder='.')
DB_NAME = "users.db"

# --- SMTP AYARLARI (GMAIL ÖRNEĞİ) ---
# Gerçek mail göndermek için burayı doldurmalısınız.
# Doldurmazsanız kod KONSOLA yazılır.
SMTP_EMAIL = ""          # Örn: "benimmailim@gmail.com"
SMTP_PASSWORD = ""       # Örn: "google-app-password" (Normal şifre değil!)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Veritabanını Başlat
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        # Kullanıcılar Tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        # Doğrulama Kodları Tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS verification_codes (
                email TEXT PRIMARY KEY,
                code TEXT NOT NULL
            )
        ''')
        conn.commit()

init_db()

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/ssh')
def ssh_page():
    # Eski SSH sayfasını koruyalım
    try:
        ssh_path = os.path.expanduser('~/.ssh/id_rsa.pub')
        if os.path.exists(ssh_path):
            with open(ssh_path, 'r') as f:
                return f"<pre>{f.read()}</pre>"
        return "SSH Anahtarı yok."
    except: return "Hata"

# --- API: DOĞRULAMA KODU GÖNDER ---
@app.route('/api/send-code', methods=['POST'])
def send_code():
    data = request.json
    email = data.get('email')
    username = data.get('username')

    if not email or not username:
        return jsonify({"error": "E-posta gerekli"}), 400

    # Kullanıcı zaten var mı?
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ? OR username = ?", (email, username))
        if cursor.fetchone():
            return jsonify({"error": "Bu kullanıcı adı veya e-posta zaten kayıtlı."}), 409

    # 6 Haneli Kod Üret
    code = str(random.randint(100000, 999999))

    # Kodu veritabanına kaydet (Varsa güncelle)
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO verification_codes (email, code) VALUES (?, ?)", (email, code))
        conn.commit()

    # Mail Gönderme İşlemi
    try:
        if SMTP_EMAIL and SMTP_PASSWORD:
            msg = MIMEText(f"Merhaba {username},\n\nAkıllı Mangala kayıt kodunuz: {code}\n\nİyi oyunlar!")
            msg['Subject'] = "Mangala Doğrulama Kodu"
            msg['From'] = SMTP_EMAIL
            msg['To'] = email

            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_EMAIL, SMTP_PASSWORD)
                server.sendmail(SMTP_EMAIL, email, msg.as_string())
            print(f"Mail gönderildi: {email} -> {code}")
        else:
            # SMTP ayarı yoksa konsola yaz (Test için)
            print(f"⚠️ [SİMÜLASYON] Mail Ayarlı Değil. {email} için kod: {code}")
            
        return jsonify({"message": "Kod gönderildi."}), 200
    except Exception as e:
        print(f"Mail Hatası: {e}")
        # Hata olsa bile simülasyon olarak başarılı dönüyoruz ki kullanıcı test edebilsin
        # Gerçek canlı ortamda burası hata dönmeli.
        print(f"⚠️ [HATA SONRASI SİMÜLASYON] {email} için kod: {code}")
        return jsonify({"message": "Kod gönderildi (Simüle)."}), 200

# --- API: KODU DOĞRULA VE KAYDET ---
@app.route('/api/verify-register', methods=['POST'])
def verify_register():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    code = data.get('code')

    if not all([username, email, password, code]):
        return jsonify({"error": "Eksik bilgi."}), 400

    # Kodu kontrol et
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT code FROM verification_codes WHERE email = ?", (email,))
        record = cursor.fetchone()

        if not record or record[0] != code:
            return jsonify({"error": "Geçersiz veya hatalı kod."}), 400

        # Kod doğru, kullanıcıyı kaydet
        hashed_pw = generate_password_hash(password)
        try:
            cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", (username, email, hashed_pw))
            # Kullanılan kodu sil
            cursor.execute("DELETE FROM verification_codes WHERE email = ?", (email,))
            conn.commit()
            return jsonify({"message": "Kayıt başarılı."}), 201
        except sqlite3.IntegrityError:
            return jsonify({"error": "Kullanıcı zaten var."}), 409

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
    
    if user and check_password_hash(user[0], password):
        return jsonify({"message": "Giriş başarılı", "username": username}), 200
    else:
        return jsonify({"error": "Hatalı giriş."}), 401

if __name__ == '__main__':
    app.run(debug=True)
