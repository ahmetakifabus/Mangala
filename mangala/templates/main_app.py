import os
import random
import sqlite3
import smtplib
from flask import Flask, request, jsonify, send_file
from email.mime.text import MIMEText
from werkzeug.security import generate_password_hash, check_password_hash
import google.generativeai as genai

app = Flask(__name__, template_folder='.')

# --- AYARLAR ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "users_v2.db")

# 1. E-POSTA AYARLARI (GMAIL)
SMTP_EMAIL = ""          # Örn: "mailin@gmail.com"
SMTP_PASSWORD = ""       # Örn: "google-app-password" (16 haneli kod)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# 2. GEMINI API AYARI
# Buraya Google AI Studio'dan aldığın API Key'i yapıştır
GEMINI_API_KEY = "" 

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-2.0-flash')

# --- VERİTABANI KURULUMU ---
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

# --- ANA SAYFA ---
@app.route('/')
def index():
    return send_file('index.html')

# --- API: SSH ANAHTARINI GÖSTER ---
@app.route('/ssh')
def ssh_page():
    try:
        ssh_path = os.path.expanduser('~/.ssh/id_rsa.pub')
        if os.path.exists(ssh_path):
            with open(ssh_path, 'r') as f:
                return f"""
                <div style="font-family: monospace; max-width: 800px; margin: 50px auto; padding: 20px; border: 1px solid #ccc; background: #f9f9f9;">
                    <h3>SSH Anahtarınız:</h3>
                    <textarea style="width:100%; height:150px;">{f.read()}</textarea>
                </div>
                """
        return "SSH Anahtarı bulunamadı. Konsoldan 'ssh-keygen' çalıştırın."
    except: return "Hata oluştu."

# --- API: GEMINI'YE SOR ---
@app.route('/api/ask-gemini', methods=['POST'])
def ask_gemini():
    if not GEMINI_API_KEY:
        return jsonify({"error": "Sunucuda API anahtarı eksik."}), 500
        
    try:
        data = request.json
        prompt = data.get('prompt')
        # Gemini'ye sor
        response = gemini_model.generate_content(prompt)
        return jsonify({"text": response.text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- API: DOĞRULAMA KODU GÖNDER ---
@app.route('/api/send-code', methods=['POST'])
def send_code():
    try:
        data = request.json
        email = data.get('email')
        username = data.get('username')

        if not email or not username:
            return jsonify({"error": "E-posta ve kullanıcı adı gerekli"}), 400

        # Kullanıcı kontrolü
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE email = ? OR username = ?", (email, username))
            if cursor.fetchone():
                return jsonify({"error": "Bu kullanıcı adı veya e-posta zaten kayıtlı."}), 409

        # Kod üret ve kaydet
        code = str(random.randint(100000, 999999))
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO verification_codes (email, code) VALUES (?, ?)", (email, code))
            conn.commit()

        # Mail Gönder
        if SMTP_EMAIL and SMTP_PASSWORD:
            try:
                msg = MIMEText(f"Merhaba {username},\n\nAkıllı Mangala kayıt kodunuz: {code}\n\nİyi oyunlar!")
                msg['Subject'] = "Mangala Doğrulama Kodu"
                msg['From'] = SMTP_EMAIL
                msg['To'] = email

                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                    server.starttls()
                    server.login(SMTP_EMAIL, SMTP_PASSWORD)
                    server.sendmail(SMTP_EMAIL, email, msg.as_string())
                print(f"Mail gönderildi: {email}")
            except Exception as e:
                print(f"SMTP Hatası: {e}")
                print(f"⚠️ [YEDEK] Mail gönderilemedi. Kod: {code}") # Log dosyasına yazar
                return jsonify({"error": "Mail sunucusuna bağlanılamadı. Bilgilerinizi kontrol edin."}), 500
        else:
            print(f"⚠️ [SİMÜLASYON] Mail ayarlı değil. {email} için kod: {code}")
            
        return jsonify({"message": "Kod gönderildi."}), 200

    except Exception as e:
        return jsonify({"error": f"Sunucu hatası: {str(e)}"}), 500

# --- API: KAYIT OL (KOD DOĞRULAMA İLE) ---
@app.route('/api/verify-register', methods=['POST'])
def verify_register():
    try:
        data = request.json
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        code = data.get('code')

        if not all([username, email, password, code]):
            return jsonify({"error": "Eksik bilgi."}), 400

        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT code FROM verification_codes WHERE email = ?", (email,))
            record = cursor.fetchone()

            if not record or record[0] != code:
                return jsonify({"error": "Hatalı veya geçersiz kod."}), 400

            hashed_pw = generate_password_hash(password)
            try:
                cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", (username, email, hashed_pw))
                cursor.execute("DELETE FROM verification_codes WHERE email = ?", (email,))
                conn.commit()
            except sqlite3.IntegrityError:
                return jsonify({"error": "Kullanıcı zaten var."}), 409

        return jsonify({"message": "Kayıt başarılı."}), 201

    except Exception as e:
        return jsonify({"error": f"Kayıt hatası: {str(e)}"}), 500

# --- API: GİRİŞ YAP ---
@app.route('/api/login', methods=['POST'])
def login():
    try:
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
            return jsonify({"error": "Kullanıcı adı veya şifre hatalı."}), 401
    except Exception as e:
        return jsonify({"error": f"Giriş hatası: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
