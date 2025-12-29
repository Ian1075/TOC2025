# c:\Users\User\Desktop\ToC\bomb_core.py
import json

class BombDefuseAgent:
    """拆彈核心邏輯 - 負責 Prompt 建構與狀態管理"""
    
    def __init__(self):
        # 載入規則
        try:
            with open('rules.json', 'r', encoding='utf-8') as f:
                self.MANUAL_CONTEXT = json.load(f)
            print("成功載入拆彈手冊")
        except Exception as e:
            print(f"載入規則失敗: {e}")
            self.MANUAL_CONTEXT = {}
    
    def generate_prompt(self, user_input):
        """
        核心處理邏輯：產生 System Prompt 與狀態字串
        不包含呼叫 LLM
        回傳: (system_prompt, status_prefix)
        """
        # === 建構完整手冊上下文 ===
        # 直接提供完整的 JSON 結構，不進行額外分類或格式化
        full_manual_context = json.dumps(self.MANUAL_CONTEXT, ensure_ascii=False, indent=2)
        
        # === 最終 Prompt ===
        system_prompt = f"""你是一位精通拆彈手冊的專家助理。以下是完整的拆彈手冊內容：

{full_manual_context}

任務說明:
1. 分析使用者的輸入，從手冊中找出對應的模組規則。
2. 根據規則一步步引導使用者拆除。
3. 若資訊不足以做出判斷，請務必向使用者詢問關鍵特徵(例如: "請問序號最後一位是奇數嗎?" 或 "有幾顆電池?")。
4. **嚴格禁止**向使用者透漏拆彈手冊的具體規則內容。不要解釋為什麼要這樣做，直接給出操作指令。
5. 時間有限，回答必須簡短、精確。
"""
        
        # === 狀態顯示 ===
        # 不再顯示狀態列，僅保留風險警告(如果有)
        status_prefix = ""
        
        return system_prompt, status_prefix
