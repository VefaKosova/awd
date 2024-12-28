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

app = Flask(__name__)

# Global progress tracker
progress = Value('d', 0.0)


def calculate_total_combinations(max_length, chars):
    return sum(len(chars) ** i for i in range(1, max_length + 1))


def crack_chunk(args):
    chars, start_idx, chunk_size, target_hash, length, total_combinations = args
    combinations = itertools.product(chars, repeat=length)

    try:
        for _ in range(start_idx):
            next(combinations)
    except StopIteration:
        return None

    length_weight = (len(chars) ** length) / total_combinations
    progress_increment = (length_weight * 100) / (chunk_size * cpu_count())

    for i in range(chunk_size):
        try:
            guess = ''.join(next(combinations))
            if hashlib.md5(guess.encode()).hexdigest() == target_hash:
                return guess
            if i % 100 == 0:
                with progress.get_lock():
                    progress.value += progress_increment
        except StopIteration:
            break
    return None


@app.route('/progress')
def progress_stream():
    def generate():
        last_progress = -1
        while progress.value < 100:
            current_progress = progress.value
            if current_progress != last_progress:
                last_progress = current_progress
                yield f"data: {min(current_progress, 100):.2f}\n\n"
            time.sleep(0.1)
        yield "data: done\n\n"
    return Response(generate(), mimetype='text/event-stream')


def parallel_brute_force(target_hash, max_length=8, processes=None):
    if processes is None:
        processes = cpu_count()
    chars = string.ascii_letters + string.digits
    chunk_size = 10000
    total_combinations = calculate_total_combinations(max_length, chars)

    with ProcessPoolExecutor(max_workers=processes) as executor:
        for length in range(1, max_length + 1):
            total_for_length = len(chars) ** length
            chunks = [(chars, i, chunk_size, target_hash, length, total_combinations)
                      for i in range(0, total_for_length, chunk_size)]

            for result in executor.map(crack_chunk, chunks):
                if result:
                    return result
    return None


async def async_generate_password():
    try:
        os.makedirs('data', exist_ok=True)

        password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        hash_value = hashlib.md5(password.encode()).hexdigest()

        with open("data/password.json", "w") as f:
            json.dump({"hash": hash_value}, f)

        return password, hash_value
    except Exception as e:
        raise RuntimeError(f"Error generating password: {e}")


@app.route("/")
def index():
    return render_template('index.html')


@app.route("/get_password", methods=["GET"])
async def get_password():
    password, hash_value = await async_generate_password()
    return jsonify({"password": password, "md5_hash": hash_value})


@app.route("/crack_and_check", methods=["POST"])
async def crack_and_check():
    try:
        with progress.get_lock():
            progress.value = 0.0

        if not os.path.exists("data/password.json"):
            password, hash_value = await async_generate_password()
        else:
            with open("data/password.json", "r") as f:
                stored_data = json.load(f)
                target_hash = stored_data["hash"]

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
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)