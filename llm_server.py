# c:\Users\User\Desktop\ToC\llm_server.py
from flask import Flask, request, jsonify
import requests
import json
import re

from bomb_core import BombDefuseAgent

app = Flask(__name__)

# 用來儲存對話紀錄的字典 (Key: user_name, Value: list of messages)
conversation_history = {}

def load_config(): # 載入設定檔
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("錯誤: 找不到 config.json。請將 config.example.json 複製為 config.json 並填入設定。")
        return {}
    except Exception as e:
        print(f"讀取設定檔失敗: {e}")
        return {}

config = load_config()
LLM_URL = config.get("llmurl", "")
API_KEY = config.get("apikey", "")
MODEL_NAME = config.get("model", "gpt-oss:20b")

# 初始化拆彈專家 Agent
bomb_agent = BombDefuseAgent()

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_text = data.get('text')
    user_name = data.get('user_name')
    
    print(f"收到來自 {user_name} 的訊息: {user_text}")

    if not user_text:
        return jsonify({"reply": "沒有收到文字"}), 400

    # --- 炸彈狀態更新 (被動擷取) ---
    # 不再強制攔截指令，而是擷取資訊後繼續讓 LLM 處理
    text_lower = user_text.lower()
    
    # 指令: 重置 (這還是需要攔截，因為要清空歷史)
    if any(keyword in text_lower for keyword in ["重置", "新炸彈", "重來"]):
        conversation_history.pop(user_name, None)
        return jsonify({"reply": "炸彈狀態已重置，請告訴我您看到了什麼？"})

    # --- 記憶功能處理 ---
    if user_name not in conversation_history:
        conversation_history[user_name] = []

    # 將使用者訊息加入紀錄
    conversation_history[user_name].append(f"User: {user_text}")

    # 限制紀錄長度 (保留最近 20 句，約 10 輪對話)
    if len(conversation_history[user_name]) > 20:
        conversation_history[user_name] = conversation_history[user_name][-20:]

    # --- 使用 BombDefuseAgent 生成 Prompt ---
    system_prompt, status_prefix = bomb_agent.generate_prompt(user_text)

    # 處理 API URL (改為 /api/generate)
    target_url = LLM_URL
    if not target_url.endswith('/api/generate'):
         target_url = f"{target_url.rstrip('/')}/api/generate"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    # 組合 Prompt：System Prompt + 歷史紀錄 + Assistant 引導
    history_text = "\n".join(conversation_history[user_name])
    # 使用 /api/generate 時，通常需要 prompt 欄位而非 messages
    full_prompt = f"{system_prompt}\n\n{history_text}\nAssistant:"
    payload = {
        "model": MODEL_NAME,
        "prompt": full_prompt,
        "stream": False
    }

    try:
        # 呼叫外部 LLM API
        response = requests.post(target_url, headers=headers, json=payload, timeout=60)
        
        if response.status_code != 200:
            print(f"上游 API 錯誤 ({response.status_code}): {response.text}")
            return jsonify({"reply": f"API 請求失敗: {response.status_code}"}), 500

        result = response.json()
        
        # 解析回應 (支援 /api/generate 的 response 欄位)
        if 'response' in result:
            reply = result['response']
        elif 'choices' in result:
            reply = result['choices'][0].get('message', {}).get('content', "")
        else:
            reply = "無法解析回應"
        
        # 將機器人回應加入紀錄，這樣下次對話時機器人就會記得自己說過什麼
        conversation_history[user_name].append(f"Assistant: {reply}")

        # 加上狀態前綴 (例如電池數量、錯誤次數)
        if status_prefix:
            final_reply = f"{status_prefix}\n{reply}"
        else:
            final_reply = reply

        print("-" * 20)
        print(f"System Prompt:\n{system_prompt[:300]}...") # 印出部分 prompt 供除錯
        print(f"LLM 回覆: {final_reply}")
        return jsonify({"reply": final_reply})

    except Exception as e:
        print(f"LLM 呼叫錯誤: {e}")
        return jsonify({"reply": "我現在有點忙，請稍後再試。"}), 500

if __name__ == '__main__':
    print(f"LLM Server 啟動中... (Target: {LLM_URL})")
    app.run(host='127.0.0.1', port=5000)
