import hashlib
import random
import string
import time
import asyncio
import itertools
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, render_template_string, jsonify

app = Flask(__name__)

# HTML template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>MD5 Cracker</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            max-width: 800px; 
            margin: 0 auto; 
            padding: 20px;
        }
        .container { 
            background-color: #f5f5f5; 
            padding: 20px; 
            border-radius: 5px;
        }
        .result {
            margin-top: 20px;
            padding: 10px;
            border-radius: 5px;
        }
        .success { background-color: #dff0d8; }
        .error { background-color: #f2dede; }
        button {
            background-color: #4CAF50;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            margin: 5px;
        }
        button:hover { background-color: #45a049; }
        .method-select {
            padding: 10px;
            margin: 10px 0;
        }
    </style>
    <script>
        async function getRandomHash() {
            const response = await fetch('/generate');
            const data = await response.json();
            document.getElementById('md5_hash').value = data.hash;
            document.getElementById('original_password').textContent = `Original Password: ${data.password}`;
        }

        async function crackHash() {
            const hash = document.getElementById('md5_hash').value;
            const method = document.getElementById('crack_method').value;
            const resultDiv = document.getElementById('result');
            
            resultDiv.className = 'result';
            resultDiv.textContent = 'Cracking in progress...';
            
            const response = await fetch('/crack', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    hash: hash,
                    method: method
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                resultDiv.className = 'result success';
                resultDiv.textContent = `Found password: ${data.password} (took ${data.time} seconds using ${method})`;
            } else {
                resultDiv.className = 'result error';
                resultDiv.textContent = `Failed to crack hash: ${data.error}`;
            }
        }
    </script>
</head>
<body>
    <div class="container">
        <h1>MD5 Hash Cracker</h1>
        
        <div>
            <button onclick="getRandomHash()">Generate Random Hash</button>
            <p id="original_password"></p>
        </div>
        
        <div style="margin: 20px 0;">
            <input type="text" id="md5_hash" placeholder="Enter MD5 hash" style="width: 300px; padding: 5px;">
            <select id="crack_method" class="method-select">
                <option value="thread">Thread</option>
                <option value="async">Async</option>
            </select>
            <button onclick="crackHash()">Crack Hash</button>
        </div>
        
        <div id="result" class="result"></div>
    </div>
</body>
</html>
"""

class MD5Cracker:
    def __init__(self, hash_to_crack: str, min_length: int = 1, max_length: int = 6):
        self.hash_to_crack = hash_to_crack.lower()
        self.min_length = min_length
        self.max_length = max_length
        self.chars = string.ascii_lowercase + string.digits
        self.found_password = None
        self.stop_flag = False

    def check_password(self, password: str) -> bool:
        if self.stop_flag:
            return False
        hashed = hashlib.md5(password.encode()).hexdigest()
        if hashed == self.hash_to_crack:
            self.found_password = password
            self.stop_flag = True
            return True
        return False

    def generate_passwords(self, length):
        return [''.join(p) for p in itertools.product(self.chars, repeat=length)]

    def crack_with_threads(self, num_threads: int = 4):
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            for length in range(self.min_length, self.max_length + 1):
                if self.stop_flag:
                    break
                passwords = self.generate_passwords(length)
                futures = [executor.submit(self.check_password, pwd) for pwd in passwords]
                for future in futures:
                    if future.result():
                        return self.found_password
        return None

    async def _async_check_password(self, password: str):
        if not self.stop_flag:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self.check_password, password)
            if result:
                return password
        return None

    async def crack_with_async(self):
        for length in range(self.min_length, self.max_length + 1):
            if self.stop_flag:
                break
            passwords = self.generate_passwords(length)
            # Şifreleri chunk'lara bölelim
            chunk_size = 1000
            password_chunks = [passwords[i:i + chunk_size] for i in range(0, len(passwords), chunk_size)]
            
            for chunk in password_chunks:
                if self.stop_flag:
                    break
                # Her chunk için async task oluştur
                tasks = [self._async_check_password(pwd) for pwd in chunk]
                results = await asyncio.gather(*tasks)
                
                # Sonuçları kontrol et
                for result in results:
                    if result:
                        return result
        return None

def generate_random_password(length=4):
    """Generate a random password and its MD5 hash"""
    chars = string.ascii_lowercase + string.digits
    password = ''.join(random.choice(chars) for _ in range(length))
    md5_hash = hashlib.md5(password.encode()).hexdigest()
    return password, md5_hash

@app.route('/')
def index():
    """Render the main page"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/generate')
def generate_hash():
    """Generate a random password and its hash"""
    password, md5_hash = generate_random_password()
    return jsonify({
        'password': password,
        'hash': md5_hash
    })

@app.route('/crack', methods=['POST'])
async def crack_hash():
    """Attempt to crack the provided MD5 hash"""
    try:
        data = request.get_json()
        md5_hash = data.get('hash', '').strip()
        method = data.get('method', 'thread')

        if not md5_hash:
            return jsonify({
                'success': False,
                'error': 'No hash provided'
            })

        if not all(c in string.hexdigits for c in md5_hash) or len(md5_hash) != 32:
            return jsonify({
                'success': False,
                'error': 'Invalid MD5 hash'
            })

        start_time = time.time()
        cracker = MD5Cracker(md5_hash)
        
        if method == 'async':
            password = await cracker.crack_with_async()
        else:  # thread
            password = cracker.crack_with_threads()
            
        elapsed_time = time.time() - start_time

        if password:
            return jsonify({
                'success': True,
                'password': password,
                'time': f'{elapsed_time:.2f}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Could not crack hash'
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == '__main__':
    # Flask uygulamasını async olarak çalıştırmak için
    app.run(debug=True, use_reloader=False)