from flask import Flask, request, jsonify, send_file
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder='.')
DB_NAME = "users.db"

# Veritabanını Başlat (Otomatik çalışır)
def init_db():
    if not os.path.exists(DB_NAME):
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL
                )
            ''')
            conn.commit()
            print("Veritabanı oluşturuldu.")

init_db()

@app.route('/')
def index():
    return send_file('index.html')

# --- API ENDPOINTS ---

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"error": "Kullanıcı adı ve şifre zorunludur"}), 400
    
    # Şifreyi güvenli hale getir (Hash'le)
    hashed_pw = generate_password_hash(password)
    
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_pw))
            conn.commit()
        return jsonify({"message": "Kayıt başarılı! Şimdi giriş yapabilirsiniz."}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Bu kullanıcı adı zaten kullanılıyor."}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
        return jsonify({"error": "Kullanıcı adı veya şifre hatalı."}), 401

if __name__ == '__main__':
    app.run(debug=True)
