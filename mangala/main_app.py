from flask import Flask, send_file
import os

# "index.html" dosyasının bu dosya ile AYNI KLASÖRDE olduğunu varsayıyoruz.
# template_folder='.' demek, "bu klasöre bak" demektir.
app = Flask(__name__, template_folder='~/mysite/templates')

@app.route('/')
def index():
    # Direkt olarak HTML dosyasını okuyup gönderir
    try:
        return send_file('index.html')
    except Exception as e:
        return f"Hata: index.html dosyası bulunamadı. Lütfen yüklediğinizden emin olun.<br>Hata detayı: {e}"

if __name__ == '__main__':
    app.run(debug=True)
