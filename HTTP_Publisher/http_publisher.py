import pandas as pd
import requests
import time
from datetime import datetime
import threading 

URL_32 = "http://127.0.0.1:5001/api/analyze"      # 3.2 算法接口
URL_34 = "http://127.0.0.1:5002/api/chat"         # 3.4 Agent 接口

FILE_INT = r"C:\Users\cww36\Downloads\human_activity_sensor_data_in_home_environment\human_activity_raw_sensor_data\sensor_sample_int.csv"
FILE_FLOAT = r"C:\Users\cww36\Downloads\human_activity_sensor_data_in_home_environment\human_activity_raw_sensor_data\sensor_sample_float.csv"

SPEED_RATE = 100 

def send_to_32(data_payload):
    try:
        payload = {
            "request_type": "sensor_data_input",
            "timestamp": datetime.now().isoformat(),
            "source": "module_3_1",
            "data": [data_payload] 
        }
        res = requests.post(URL_32, json=payload, timeout=2)
        sensor_id = data_payload['sensor_id']
        value = data_payload['value']
        if res.status_code == 200:
            print(f"[安全基线] 数据已入算 | {sensor_id} 数值: {value} | 状态: 正常")
        else:
            print(f"[安全基线] 处理延迟 | {sensor_id} | HTTP: {res.status_code}")
            
    except Exception as e:
        print(f"系统警报] 算法服务离线 | 无法分析传感器数据 | 错误: {e}")


def send_to_34(text_payload):
    try:
        payload = {
            "msg_type": "sensor_event",
            "content": text_payload, 
            "timestamp": datetime.now().isoformat()
        }
        res = requests.post(URL_34, json=payload, timeout=2)
        
        event_brief = text_payload.replace("【传感器事件】", "").split("，")[1] # 提取关键信息
        if res.status_code == 200:
            print(f"[亲情日志] 记忆存档 | {event_brief} | 状态: 已记录")
        else:
            print(f"[亲情日志] 存档失败 | {event_brief} | HTTP: {res.status_code}")

    except Exception as e:
        print(f"系统警报] AI 助手失联 | 无法生成关怀日报 | 错误: {e}")


def process_file(file_path, is_int):
    chunk_iter = pd.read_csv(file_path, chunksize=50)
    prev_time = None

    for chunk in chunk_iter:
        for _, row in chunk.iterrows():
            try:
                # --- 数据清洗 ---
                ts_str = str(row['timestamp'])
                sensor_id = str(row['sensor_id'])
                raw_val = row['value']
                if pd.isna(raw_val): continue

                # --- 时间控制 ---
                try:
                    curr_time = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    if prev_time:
                        sleep_sec = (curr_time - prev_time).total_seconds() / SPEED_RATE
                        if sleep_sec > 0: time.sleep(sleep_sec)
                    prev_time = curr_time
                except: pass

                # --- 核心逻辑：根据数据类型构建不同的 Payload ---
                if is_int:
                    state = "开启" if int(raw_val) == 1 else "关闭"
                    value_type = "INT"
                    desc_text = f"【传感器事件】{ts_str}，传感器 {sensor_id} 状态变为 {state}。"
                else:
                    value_type = "FLOAT"
                    desc_text = f"【传感器事件】{ts_str}，传感器 {sensor_id} 读数为 {raw_val:.2f}。"

                # 1. 构建发给 3.2 的数据 (结构化)
                data_32 = {
                    "sensor_id": sensor_id,
                    "node_id": f"NODE_{sensor_id}",
                    "timestamp": ts_str,
                    "value": int(raw_val) if is_int else float(raw_val),
                    "data_type": value_type,
                    "location": f"Room_{sensor_id[0]}",
                    "function": "motion" if is_int else "current"
                }

                # 2. 构建发给 3.4 的数据 (自然语言)
                data_34 = desc_text

                # --- 并发发送 ---
                threading.Thread(target=send_to_32, args=(data_32,), daemon=True).start()
                threading.Thread(target=send_to_34, args=(data_34,), daemon=True).start()

                action = "状态变更" if is_int else "数值读取"
                print(f"[微感知] 正在传输 | {sensor_id} | {action}: {raw_val} | 时间: {ts_str}")

            except Exception as e:
                print(f"[数据清洗] 跳过脏数据 | 无法解析该行记录 | 错误: {e}")


if __name__ == "__main__":
    print("[独居关怀系统] 模拟器启动")
    print("正在加载微感知数据引擎...")
    print(f"   模拟速度: {SPEED_RATE}倍速")
    print("-" * 50)

    t1 = threading.Thread(target=process_file, args=(FILE_INT, True))
    t2 = threading.Thread(target=process_file, args=(FILE_FLOAT, False))

    t1.start()
    t2.start()
    t1.join()
    t2.join()
    
    print("[系统提示] 模拟数据发送完毕，系统保持待机")
