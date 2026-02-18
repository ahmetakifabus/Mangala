import os
import random
import sqlite3
import smtplib
import json
import time
from flask import Flask, request, jsonify, send_file
from email.mime.text import MIMEText
from werkzeug.security import generate_password_hash, check_password_hash
import google.generativeai as genai

app = Flask(__name__, template_folder='.')

# --- AYARLAR ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "mangala_online.db") # Yeni DB

# 1. E-POSTA AYARLARI (GMAIL)
SMTP_EMAIL = "" 
SMTP_PASSWORD = ""
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# 2. GEMINI API AYARI
GEMINI_API_KEY = "" 

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-2.0-flash')

# --- VERİTABANI ---
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS verification_codes (
                email TEXT PRIMARY KEY,
                code TEXT NOT NULL
            )
        ''')
        # Lobi/Oyun Tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS games (
                lobby_id TEXT PRIMARY KEY,
                p1_username TEXT,
                p2_username TEXT,
                board TEXT, -- JSON Array
                turn TEXT, -- 'p1' veya 'p2'
                status TEXT, -- 'waiting', 'playing', 'ended'
                winner TEXT,
                last_move_time REAL
            )
        ''')
        conn.commit()

init_db()

# --- MANGALA OYUN MANTIĞI (PYTHON) ---
INITIAL_BOARD = [4, 4, 4, 4, 4, 4, 0, 4, 4, 4, 4, 4, 4, 0]

def check_game_over(board):
    p1_empty = all(x == 0 for x in board[0:6])
    p2_empty = all(x == 0 for x in board[7:13])
    
    if p1_empty or p2_empty:
        final_board = list(board)
        p1_total = final_board[6]
        p2_total = final_board[13]
        
        # Kalan taşları topla
        if p1_empty:
            remaining = sum(final_board[7:13])
            for i in range(7, 13): final_board[i] = 0
            p1_total += remaining
            final_board[6] = p1_total
        else:
            remaining = sum(final_board[0:6])
            for i in range(0, 6): final_board[i] = 0
            p2_total += remaining
            final_board[13] = p2_total
            
        winner = 'p1' if p1_total > p2_total else ('p2' if p2_total > p1_total else 'draw')
        return True, final_board, winner
    return False, board, None

def execute_move_logic(board, index, player_role):
    # player_role: 'p1' (0-5) veya 'p2' (7-12)
    # index: 0-13 arası kuyu indeksi
    
    # Yetki kontrolü
    if player_role == 'p1' and not (0 <= index <= 5): return None
    if player_role == 'p2' and not (7 <= index <= 12): return None
    if board[index] == 0: return None

    new_board = list(board)
    seeds = new_board[index]
    new_board[index] = 0
    pos = index

    if seeds == 1:
        pos = (pos + 1) % 14
        new_board[pos] += 1
    else:
        new_board[pos] += 1
        seeds -= 1
        while seeds > 0:
            pos = (pos + 1) % 14
            # Rakip hazineyi atla
            if (player_role == 'p1' and pos == 13) or (player_role == 'p2' and pos == 6):
                continue
            new_board[pos] += 1
            seeds -= 1

    next_turn = 'p2' if player_role == 'p1' else 'p1'
    message = ""

    # Kural 1: Son taş hazineye
    is_treasury = (player_role == 'p1' and pos == 6) or (player_role == 'p2' and pos == 13)
    if is_treasury:
        next_turn = player_role # Sıra tekrar oynayanda
    
    # Kural 2: Çift yapma (Rakip bölgede)
    elif new_board[pos] % 2 == 0:
        is_opponent_side = (player_role == 'p1' and 7 <= pos <= 12) or (player_role == 'p2' and 0 <= pos <= 5)
        if is_opponent_side:
            treasury = 6 if player_role == 'p1' else 13
            new_board[treasury] += new_board[pos]
            new_board[pos] = 0
    
    # Kural 3: Boş kuyu (Kendi bölgende)
    elif new_board[pos] == 1:
        is_own_side = (player_role == 'p1' and 0 <= pos <= 5) or (player_role == 'p2' and 7 <= pos <= 12)
        if is_own_side:
            opposite = 12 - pos
            if new_board[opposite] > 0:
                treasury = 6 if player_role == 'p1' else 13
                total = new_board[pos] + new_board[opposite]
                new_board[treasury] += total
                new_board[pos] = 0
                new_board[opposite] = 0

    return {"board": new_board, "turn": next_turn}

# --- ROUTES ---
@app.route('/')
def index(): return send_file('index.html')

# --- ONLINE LOBİ API ---

@app.route('/api/create-lobby', methods=['POST'])
def create_lobby():
    data = request.json
    username = data.get('username')
    lobby_id = str(random.randint(1000, 9999))
    
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO games (lobby_id, p1_username, board, turn, status, last_move_time)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (lobby_id, username, json.dumps(INITIAL_BOARD), 'p1', 'waiting', time.time()))
        conn.commit()
    
    return jsonify({"lobby_id": lobby_id, "role": "p1"})

@app.route('/api/join-lobby', methods=['POST'])
def join_lobby():
    data = request.json
    username = data.get('username')
    lobby_id = data.get('lobby_id')
    
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        # Lobi var mı ve boş mu?
        cursor.execute("SELECT p1_username, p2_username FROM games WHERE lobby_id = ?", (lobby_id,))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({"error": "Lobi bulunamadı."}), 404
        
        if row[1]: # p2_username doluysa
            return jsonify({"error": "Lobi dolu."}), 409
            
        # Katıl
        cursor.execute("UPDATE games SET p2_username = ?, status = 'playing', last_move_time = ? WHERE lobby_id = ?", 
                      (username, time.time(), lobby_id))
        conn.commit()
        
    return jsonify({"lobby_id": lobby_id, "role": "p2", "opponent": row[0]})

@app.route('/api/join-random', methods=['POST'])
def join_random():
    username = data = request.json.get('username')
    
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        # Bekleyen oyun bul (kendiminkiler hariç)
        cursor.execute("SELECT lobby_id, p1_username FROM games WHERE status = 'waiting' AND p1_username != ?", (username,))
        games = cursor.fetchall()
        
        if games:
            # Rastgele birine katıl
            selected_game = random.choice(games)
            lobby_id = selected_game[0]
            
            cursor.execute("UPDATE games SET p2_username = ?, status = 'playing', last_move_time = ? WHERE lobby_id = ?", 
                          (username, time.time(), lobby_id))
            conn.commit()
            return jsonify({"lobby_id": lobby_id, "role": "p2", "found": True})
        
        else:
            # Oyun yoksa yeni oluştur
            lobby_id = str(random.randint(1000, 9999))
            cursor.execute('''
                INSERT INTO games (lobby_id, p1_username, board, turn, status, last_move_time)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (lobby_id, username, json.dumps(INITIAL_BOARD), 'p1', 'waiting', time.time()))
            conn.commit()
            return jsonify({"lobby_id": lobby_id, "role": "p1", "found": False, "message": "Boş oda yoktu, yeni oda açıldı."})

@app.route('/api/game-state', methods=['GET'])
def game_state():
    lobby_id = request.args.get('lobby_id')
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT board, turn, status, p1_username, p2_username, winner FROM games WHERE lobby_id = ?", (lobby_id,))
        row = cursor.fetchone()
        
        if not row: return jsonify({"error": "Oyun yok"}), 404
        
        return jsonify({
            "board": json.loads(row[0]),
            "turn": row[1],
            "status": row[2],
            "p1": row[3],
            "p2": row[4],
            "winner": row[5]
        })

@app.route('/api/move', methods=['POST'])
def make_move():
    data = request.json
    lobby_id = data.get('lobby_id')
    index = data.get('index')
    role = data.get('role') # 'p1' veya 'p2'
    
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT board, turn, status FROM games WHERE lobby_id = ?", (lobby_id,))
        row = cursor.fetchone()
        
        if not row: return jsonify({"error": "Oyun yok"}), 404
        
        board = json.loads(row[0])
        current_turn = row[1]
        status = row[2]
        
        if status != 'playing': return jsonify({"error": "Oyun aktif değil"}), 400
        if current_turn != role: return jsonify({"error": "Sıra sizde değil"}), 400
        
        # Hamleyi Hesapla
        result = execute_move_logic(board, index, role)
        if not result: return jsonify({"error": "Geçersiz hamle"}), 400
        
        new_board = result['board']
        next_turn = result['turn']
        
        # Oyun Bitti mi?
        is_over, final_board, winner = check_game_over(new_board)
        
        new_status = 'ended' if is_over else 'playing'
        final_board_json = json.dumps(final_board)
        
        cursor.execute("UPDATE games SET board = ?, turn = ?, status = ?, winner = ?, last_move_time = ? WHERE lobby_id = ?", 
                      (final_board_json, next_turn, new_status, winner, time.time(), lobby_id))
        conn.commit()
        
        return jsonify({"success": True})

# --- USER & GEMINI API (Öncekilerin Aynısı) ---
@app.route('/api/ask-gemini', methods=['POST'])
def ask_gemini():
    if not GEMINI_API_KEY: return jsonify({"error": "API Key yok"}), 500
    try:
        prompt = request.json.get('prompt')
        response = gemini_model.generate_content(prompt)
        return jsonify({"text": response.text})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    username = request.json.get('username')
    password = request.json.get('password')
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
    if user and check_password_hash(user[0], password): return jsonify({"username": username})
    return jsonify({"error": "Hatalı"}), 401

@app.route('/api/send-code', methods=['POST'])
def send_code():
    # ... (Eski kodunuzun aynısı, kısaltıldı)
    return jsonify({"message": "Kod gönderildi (Simüle)"})

@app.route('/api/verify-register', methods=['POST'])
def verify_register():
    data = request.json
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        try:
            hashed_pw = generate_password_hash(data['password'])
            cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", (data['username'], data['email'], hashed_pw))
            conn.commit()
            return jsonify({"message": "Başarılı"})
        except: return jsonify({"error": "Kullanıcı var"}), 400

if __name__ == '__main__':
    app.run(debug=True)
