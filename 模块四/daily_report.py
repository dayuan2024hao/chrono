# 中间层数据处理服务（支持多位老人独立数据 + 阿里云AI + 已开跨域）
from flask import Flask, request, jsonify
import time
import re
import requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

sensor_data = {}  # 格式：{"张爷爷": [数据1, 数据2...], "李奶奶": [数据1...]}

# -------------------------- 阿里云AI配置 --------------------------
API_KEY = "sk-ba7988b3cb6a44df875e1a63d5eef9bb"
AI_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

# 加载护理知识库
knowledge_files = [
    "高血压日常护理.txt","高血压饮食建议.txt","老年跌倒预防护理.txt",
    "老年肺炎护理.txt","老年尿失禁.txt","老年认知障碍（阿尔茨海默病）护理.txt",
    "老年糖尿病护理.txt","老年压疮（褥疮护理）.txt"
]
KNOWLEDGE = ""
for file in knowledge_files:
    try:
        with open(file, "r", encoding="utf-8") as f:
            KNOWLEDGE += f.read() + "\n\n"
    except:
        pass

# 提取老人姓名（张爷爷 / 李奶奶）
def extract_elder_name(text):
    pattern = r'([\u4e00-\u9fa5]{1,2}(?:爷爷|奶奶))'
    result = re.findall(pattern, text)
    return result[0] if result else "default"

# ===================== 生成【单个老人】的日报 =====================
def generate_daily(elder_name):
    today_str = time.strftime("%Y-%m-%d")
    water = elec = door = act = 0
    abnormal = False

    # 只拿当前老人的数据，不会混其他老人
    events = sensor_data.get(elder_name, [])

    for event in events:
        if event.get("timestamp", "").startswith(today_str):
            c = event.get("content", "")
            if "用水" in c: water += 1
            if "用电" in c: elec += 1
            if "门磁" in c: door += 1
            if "活动" in c: act += 1
            if "异常" in c or "跌倒" in c: abnormal = True

    status = "异常" if abnormal else ("暂无数据" if not events else "正常")

    return f"""【亲情日报】
老人：{elder_name}
状态：{status}
用水：{water}次，用电：{elec}次
门磁：{door}次，活动：{act}小时
统计日期：{today_str}"""

# AI问答
def ai_answer(question):
    try:
        if any(word in question for word in ["日报", "怎么样", "状态", "还好吗"]):
            elder = extract_elder_name(question)
            return generate_daily(elder)

        prompt = f"你是专业养老助手，根据知识库回答：{KNOWLEDGE}\n用户问题：{question}"
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "qwen-turbo",
            "messages": [{"role":"user","content":prompt}]
        }
        print("--- 开始调用阿里云AI ---")
        print("请求地址：", AI_URL)
        print("请求头：", headers)
        print("请求体：", data)
        resp = requests.post(AI_URL, json=data, headers=headers, timeout=15)
        print("响应状态码：", resp.status_code)
        print("响应内容：", resp.text)
        print("--- 调用结束 ---")
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print("调用AI时出错：", type(e).__name__, str(e))
        return f"AI服务繁忙，请稍后再试（错误：{type(e).__name__}）"

# ===================== 接收数据：自动识别老人，分开存储 =====================
@app.route("/api/receive_event", methods=["POST"])
def receive_data():
    data = request.get_json()
    if not data:
        return jsonify(status="fail", msg="数据为空")
    
    content = data.get("content", "")
    elder = extract_elder_name(content)  # 识别是哪个老人

    # 存入对应老人的列表
    if elder not in sensor_data:
        sensor_data[elder] = []
    sensor_data[elder].append(data)

    return jsonify(status="success", msg=f"已接收 {elder} 数据")

# ===================== 获取所有老人列表（给前端用） =====================
@app.route("/api/elder_list", methods=["GET"])
def get_elder_list():
    return jsonify(elder_list=list(sensor_data.keys()))


@app.route("/api/get_result", methods=["GET"])
def send_result():
    elder = request.args.get("name", "")
    
    if not elder:
        all_report = ""
        for name in sensor_data:
            all_report += generate_daily(name) + "\n\n"
        return jsonify(downstream_output=all_report if all_report else "暂无老人数据")
    
    return jsonify(downstream_output=generate_daily(elder))

@app.route("/api/ai_chat", methods=["POST"])
def ai_chat():
    user_msg = request.json.get("question", "")  
    if not user_msg:
        return jsonify(reply="请输入你的问题")
    reply = ai_answer(user_msg)
    return jsonify(reply=reply)

# 启动服务
if __name__ == "__main__":
    print("="*60)
    print("中间层已启动 ✅ 支持多老人独立数据 ✅ 已开跨域")
    print("服务地址：http://0.0.0.0:5000")
    print("="*60)
    app.run(host="0.0.0.0", port=5000, debug=True)