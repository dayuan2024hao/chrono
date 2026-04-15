from flask import Flask, request, jsonify
from flask_cors import CORS
import requests as req_lib 
from collections import deque
import threading

app = Flask(__name__)
CORS(app)

# 3.2模块地址
TARGET_32_URL = "http://127.0.0.1:5001/api/analyze"

# 本地数据存储
data_store = deque(maxlen=2000)
data_lock = threading.Lock()

@app.route('/api/sensor_data', methods=['POST'])
def receive_sensor_data():
    try:
        json_data = request.get_json()
        if not json_data:
            return jsonify({"error": "No data"}), 400

        # --- A. 本地存储 ---
        with data_lock:
            data_store.append(json_data)

        # --- B. 转发给 3.2 模块 ---
        try:
            req_lib.post(TARGET_32_URL, json=json_data, timeout=2)
            print(f"已转发: {json_data['device_id']}")
        except Exception as e:
            print(f"转发失败 (可能 3.2 没开): {e}")

        return jsonify({"status": "success"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/latest_data', methods=['GET'])
def get_data():
    with data_lock:
        return jsonify(list(data_store)), 200

@app.route('/')
def index():
    return f"<h1>中转站后端运行中</h1><p>当前缓存: {len(data_store)} 条</p>"

if __name__ == '__main__':
    print("中转站启动: http://127.0.0.1:5000")
    app.run(port=5000, threaded=True)
