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
        
        # 模組關鍵字
        self.MODULE_KEYWORDS = {
            "簡易線路": ["線", "條", "線路"],
            "大按鈕": ["按鈕", "引爆", "按住"],
            "謎之鍵盤": ["符號", "鍵盤"],
            "四色方塊": ["四色", "方塊", "閃", "西蒙"],
            "誰在一壘": ["一壘", "螢幕", "顯示"],
            "記憶": ["記憶", "階段", "顯示器"],
            "摩斯密碼": ["摩斯", "閃爍", "頻率"],
            "複雜線路": ["複雜", "LED", "星號"],
            "線路順序": ["順序", "面板", "累計"],
            "迷宮": ["迷宮", "白點", "三角"],
            "密碼": ["密碼", "字母", "輪盤"],
            "排氣": ["排氣", "是否"],
            "電容放電": ["電容", "放電", "拉杆"],
            "旋鈕": ["旋鈕", "LED燈"],
        }
        
        # 儲存每個使用者的炸彈狀態 (Discord 用)
        self.user_states = {}
    
    def set_user_state(self, user_id, serial=None, batteries=None, indicators=None, strikes=None):
        """儲存使用者的炸彈狀態"""
        if user_id not in self.user_states:
            self.user_states[user_id] = {
                "serial": "",
                "batteries": 0,
                "indicators": "",
                "strikes": 0
            }
        
        if serial is not None: self.user_states[user_id]["serial"] = serial
        if batteries is not None: self.user_states[user_id]["batteries"] = batteries
        if indicators is not None: self.user_states[user_id]["indicators"] = indicators
        if strikes is not None: self.user_states[user_id]["strikes"] = strikes

    def get_user_state(self, user_id):
        """取得使用者的炸彈狀態"""
        return self.user_states.get(user_id, {})

    def generate_prompt(self, user_input, user_id=None):
        """
        核心處理邏輯：產生 System Prompt 與狀態字串
        不包含呼叫 LLM
        回傳: (system_prompt, status_prefix)
        """
        # === 從記憶中取得狀態 ===
        state = self.get_user_state(user_id)
        serial = state.get("serial", "")
        batteries = state.get("batteries", 0)
        indicators = state.get("indicators", "")
        strikes = state.get("strikes", 0)
        
        # === 炸彈資訊 ===
        bomb_info_text = f"""
【當前炸彈資訊】
序號: {serial if serial else "未填寫"}
電池: {batteries}顆
燈號: {indicators if indicators else "無"}
錯誤: {strikes}次
"""
        
        # === 智能判斷模組 ===
        context = self.MANUAL_CONTEXT.get("一般", "")
        
        matched_module = None
        for module_name, keywords in self.MODULE_KEYWORDS.items():
            if any(keyword in user_input for keyword in keywords):
                matched_module = module_name
                break
        
        # === 載入規則 ===
        if matched_module and matched_module in self.MANUAL_CONTEXT:
            context += "\n\n" + self.MANUAL_CONTEXT[matched_module]
        
        # === 檢查缺少資訊 ===
        missing_info = []
        needs_serial = ["簡易線路", "四色方塊", "複雜線路"]
        needs_battery = ["簡易線路", "大按鈕", "複雜線路"]
        
        if not serial and matched_module in needs_serial:
            missing_info.append("序號")
        if batteries == 0 and matched_module in needs_battery:
            missing_info.append("電池數量")
        
        if missing_info:
            context += f"\n\n缺少: {', '.join(missing_info)}。請詢問!"
        
        # === 風險警告 ===
        risk_warning = ""
        if strikes >= 2:
            risk_warning = "危險!最後1次機會!\n"
            context += "\n\n危急!給最保守建議!"
        elif strikes == 1:
            risk_warning = "已錯1次,小心\n"
        
        # === 最終 Prompt ===
        system_prompt = f"""{context}

{bomb_info_text}

提醒:
1. 直接說結論,不重複規則
2. 大按鈕要列完整4色對照表
3. 簡潔有力
"""
        
        # === 狀態顯示 ===
        # 不再顯示狀態列，僅保留風險警告(如果有)
        status_prefix = risk_warning
        
        return system_prompt, status_prefix
