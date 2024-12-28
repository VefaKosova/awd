from flask import Flask, request, jsonify, render_template, Response
import hashlib
import random
import string
import asyncio
import json
from concurrent.futures import ProcessPoolExecutor
import itertools
from multiprocessing import Value, cpu_count
import os
import time
import signal
import sys
import ctypes
from functools import lru_cache
from typing import Optional


app = Flask(__name__)

progress = Value(ctypes.c_double, 0.0, lock=True)
should_stop = Value(ctypes.c_bool, False, lock=True)


# Signal handler for graceful shutdown
def signal_handler(sig, frame):
    should_stop.value = True
    print("\nShutting down gracefully...")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


def calculate_total_combinations(max_length, chars):
    return sum(len(chars) ** i for i in range(1, max_length + 1))


@lru_cache(maxsize=256)
def get_hash(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()


def crack_chunk(args):
    chars, start_idx, chunk_size, target_hash, length, total_combinations = args
    combinations = itertools.islice(itertools.product(chars, repeat=length), start_idx, start_idx + chunk_size)
    length_weight = (len(chars) ** length) / total_combinations
    progress_increment = max((length_weight * 100) / (chunk_size * cpu_count()), 0.01)

    for i, combo in enumerate(combinations):
        if should_stop.value:
            return None
        guess = ''.join(combo)
        if get_hash(guess) == target_hash:
            should_stop.value = True
            return guess
        if i % 1000 == 0:
            with progress.get_lock():
                progress.value += progress_increment
    return None


@app.route('/progress')
def progress_stream():
    def generate():
        try:
            last_progress = -1
            while True:
                current_progress = progress.value
                if current_progress != last_progress:
                    last_progress = current_progress
                    if current_progress >= 100 or should_stop.value:
                        yield "data: done\n\n"
                        break
                    yield f"data: {min(current_progress, 100):.2f}\n\n"
                time.sleep(0.1)
        except Exception as e:
            print(f"Progress stream error: {e}")
            yield "data: error\n\n"

    return Response(generate(), mimetype='text/event-stream')

def reset_progress():
    with progress.get_lock():
        progress.value = 0.0
    should_stop.value = False

def update_progress(increment):
    with progress.get_lock():
        progress.value = min(progress.value + increment, 100.0)


def parallel_brute_force(target_hash: str, max_length: int = 8, processes: Optional[int] = None) -> Optional[str]:
    if processes is None:
        processes = cpu_count()

    chars = string.ascii_letters + string.digits
    chunk_size = max(50000 // cpu_count(), 1000)
    total_combinations = calculate_total_combinations(max_length, chars)

    with ProcessPoolExecutor(max_workers=processes) as executor:
        for length in range(1, max_length + 1):
            if should_stop.value:
                break

            total_for_length = len(chars) ** length
            chunks = [
                (chars, start_idx, min(chunk_size, total_for_length - start_idx), target_hash, length, total_combinations)
                for start_idx in range(0, total_for_length, chunk_size)
            ]

            for result in executor.map(crack_chunk, chunks):
                if result:
                    should_stop.value = True
                    return result

    return None


async def async_generate_password():
    try:
        os.makedirs("data", exist_ok=True)
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        hash_value = hashlib.md5(password.encode()).hexdigest()

        with open("data/password.json", "w") as f:
            json.dump({"hash": hash_value}, f, indent=4)  # Added indent for better readability

        return password, hash_value
    except Exception as e:
        raise RuntimeError(f"Error generating password: {e}")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/get_password", methods=["GET"])
async def get_password():
    password, hash_value = await async_generate_password()
    return jsonify({"password": password, "md5_hash": hash_value})

@app.route("/crack_and_check", methods=["POST"])
async def crack_and_check():
    try:
        with progress.get_lock():
            progress.value = 0.0
            
        target_hash = None
        
        # Check if password file exists and read hash
        if os.path.exists("data/password.json"):
            try:
                with open("data/password.json", "r") as f:
                    stored_data = json.load(f)
                    target_hash = stored_data.get("hash")
                    if not target_hash:
                        raise ValueError("Hash not found in the password file")
                    print(f"Found stored hash: {target_hash}")  # Debug log
            except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
                print(f"Error reading password file: {e}")  # Debug log
                return jsonify({"error": "Password data is missing or corrupted"}), 500
        
        # Generate new password if no hash found
        if not target_hash:
            password, target_hash = await async_generate_password()
            print(f"Generated new hash: {target_hash}")  # Debug log

        # Attempt to crack the password
        cracked_password = await asyncio.to_thread(
            parallel_brute_force,
            target_hash,
            max_length=8
        )

        if cracked_password:
            return jsonify({
                "success": True,
                "message": f"Password cracked: {cracked_password}"
            })
        return jsonify({
            "success": False,
            "message": "Password not found"
        })
    except Exception as e:
        print(f"Cracking error: {e}")  # Debug log
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", debug=True)
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        sys.exit(0)