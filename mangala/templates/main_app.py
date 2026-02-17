from flask import Flask, send_file
import os

app = Flask(__name__, template_folder='.')

@app.route('/')
def index():
    # Oyunun ana sayfası
    try:
        return send_file('index.html')
    except Exception as e:
        return f"Hata: index.html dosyası bulunamadı.<br>Detay: {e}"

# --- SSH GÖSTERME (KLAVYE DOSTU) ---
@app.route('/ssh')
def show_ssh_key():
    try:
        # Sizin kullanıcı adınıza göre anahtar yolu
        ssh_path = '/home/hizlimangala/.ssh/id_rsa.pub'
        
        if os.path.exists(ssh_path):
            with open(ssh_path, 'r') as f:
                key_content = f.read().strip()
            
            return f"""
            <div style="font-family: sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; border: 1px solid #ccc; border-radius: 10px; text-align: center;">
                <h2 style="color: #2c3e50;">🔑 SSH Anahtarınız</h2>
                
                <p style="background: #ffeaa7; padding: 10px; border-radius: 5px; font-weight: bold;">
                    👇 Kod aşağıda otomatik seçildi. Klavyeden <span style="background:white; padding:2px 5px; border:1px solid #ccc;">CTRL + C</span> yaparak kopyalayın.
                </p>
                
                <textarea id="sshInput" style="width: 100%; height: 150px; font-family: monospace; font-size: 14px; padding: 10px; border: 2px solid #2980b9; border-radius: 5px; background: #eaf2f8;" onclick="this.select()">{key_content}</textarea>
                
                <br><br>
                
                <button onclick="copyKey()" style="background-color: #27ae60; color: white; border: none; padding: 12px 24px; font-size: 16px; border-radius: 5px; cursor: pointer; font-weight: bold;">
                   📋 Tıkla ve Kopyala (Yedek Buton)
                </button>
                
                <p id="msg" style="color: green; font-weight: bold; display: none; margin-top: 10px;">✅ Kopyalandı!</p>
                <br><br>
                <a href="/">← Oyuna Dön</a>

                <script>
                    // Sayfa açılır açılmaz metni seç
                    window.onload = function() {{
                        var textArea = document.getElementById("sshInput");
                        textArea.focus();
                        textArea.select();
                    }};

                    function copyKey() {{
                        var copyText = document.getElementById("sshInput");
                        copyText.select();
                        copyText.setSelectionRange(0, 99999); 
                        
                        // Eski ve yeni yöntemleri dene
                        try {{
                            // Yöntem 1: Modern API
                            navigator.clipboard.writeText(copyText.value).then(success, tryOldMethod);
                        }} catch (err) {{
                            tryOldMethod();
                        }}
                        
                        function tryOldMethod() {{
                            try {{
                                // Yöntem 2: Eski Komut
                                document.execCommand('copy');
                                success();
                            }} catch (err) {{
                                alert("Otomatik kopyalanamadı. Lütfen CTRL+C yapın.");
                            }}
                        }}
                        
                        function success() {{
                            document.getElementById("msg").style.display = "block";
                        }}
                    }}
                </script>
            </div>
            """
        else:
            return "<h2>⚠️ Anahtar Bulunamadı</h2><p>Lütfen önce konsolda <code>ssh-keygen</code> komutunu çalıştırın.</p>"
            
    except Exception as e:
        return f"Hata oluştu: {e}"

if __name__ == '__main__':
    app.run(debug=True)
