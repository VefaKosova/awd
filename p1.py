import hashlib
import itertools
import random
import string
import time
import asyncio
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
        }
        button:hover { background-color: #45a049; }
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
            const resultDiv = document.getElementById('result');
            
            resultDiv.className = 'result';
            resultDiv.textContent = 'Cracking in progress...';
            
            const response = await fetch('/crack', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({hash: hash})
            });
            
            const data = await response.json();
            
            if (data.success) {
                resultDiv.className = 'result success';
                resultDiv.textContent = `Found password: ${data.password} (took ${data.time} seconds)`;
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

    def crack_with_threads(self, num_threads: int = 4):
        def generate_passwords(length):
            return [''.join(p) for p in itertools.product(self.chars, repeat=length)]

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            for length in range(self.min_length, self.max_length + 1):
                if self.stop_flag:
                    break
                passwords = generate_passwords(length)
                futures = [executor.submit(self.check_password, pwd) for pwd in passwords]
                for future in futures:
                    if future.result():
                        return self.found_password
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
def crack_hash():
    """Attempt to crack the provided MD5 hash"""
    try:
        data = request.get_json()
        md5_hash = data.get('hash', '').strip()

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
    app.run(debug=True)