import discord
from discord.ext import commands
import json # 匯入處理 JSON 檔案的函式庫
import asyncio
import time
import speech_recognition as sr # pip install SpeechRecognition
import audioop
import wave
from discord.ext import voice_recv # pip install discord-ext-voice-recv
import aiohttp
import logging

def load_config():
    """從 config.json 檔案載入設定"""
    try:
        # 'utf-8' 編碼可以確保正確讀取包含中文等特殊字元的檔案
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("錯誤：找不到 config.json 檔案。")
        print("請確保與 bot.py 在同一個資料夾中，並已正確命名。")
        print("提示：你可以將 config.example.json 複製並重新命名為 config.json，然後填入你的資料。")
        return None
    except json.JSONDecodeError:
        print("錯誤：config.json 檔案格式不正確。")
        print("請檢查 JSON 語法是否有效（例如，是否有多餘的逗號）。")
        return None

# --- 載入設定 ---
config = load_config()

# 如果無法成功載入設定，就結束程式
if not config:
    exit()

# 從設定檔中讀取特定值
BOT_TOKEN = config.get("token")
LLM_URL = config.get("llmurl")
#API_KEY = config.get("apikey")
COMMAND_PREFIX = config.get("prefix", "!") # 如果 json 中沒有 prefix，預設為 "!"

# 檢查 Token 是否已設定
if not BOT_TOKEN:
    print("錯誤：請在 config.json 檔案中設定你的 Discord Bot Token！")
    exit()

# --- 初始化機器人 ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# --- 事件與指令 ---
@bot.event
async def on_ready():
    """當機器人成功連線並準備就緒時觸發"""
    print(f'Logged in as {bot.user.name} (ID: {bot.user.id})')
    print('------')
    # 現在你可以使用從設定檔載入的變數
    print(f'LLM URL: {LLM_URL}')
    #print(f'API Key: {API_KEY[:4]}... (為了安全，只顯示前幾碼)')

class STTSink(voice_recv.AudioSink):
    def __init__(self, channel):
        self.channel = channel
        self.user_buffers = {}
        self.last_spoken = {}
        self.users = {}
        self.decoders = {}
        self.recognizer = sr.Recognizer()
        self.running = True
        asyncio.create_task(self.check_silence())
        print("STTSink 已啟動，準備接收語音...")

    def wants_opus(self):
        return True

    def write(self, user, data):
        if user is None: return
        user_id = user.id
        if user_id not in self.decoders:
            self.decoders[user_id] = discord.opus.Decoder()

        if user_id not in self.user_buffers:
            self.user_buffers[user_id] = bytearray()
            self.users[user_id] = user
            print(f"正在接收 {user.name} 的語音...")
            
        try:
            pcm_data = self.decoders[user_id].decode(data.opus, fec=False)
            self.user_buffers[user_id].extend(pcm_data)
            self.last_spoken[user_id] = time.time()
        except Exception as e:
            # 印出錯誤以便除錯 (如果是 corrupted stream，代表封包損毀)
            print(f"音訊解碼錯誤: {e}")

    async def check_silence(self):
        """背景任務：檢查使用者是否停止說話，並觸發辨識"""
        while self.running:
            await asyncio.sleep(1)
            now = time.time()
            for user_id, last_time in list(self.last_spoken.items()):
                if now - last_time > 1: # 超過 1 秒沒說話
                    if user_id in self.user_buffers and len(self.user_buffers[user_id]) > 0:
                        audio_data = bytes(self.user_buffers[user_id])
                        self.user_buffers[user_id] = bytearray() # 清空緩衝區
                        user = self.users.get(user_id)
                        print(f"偵測到 {user.name} 停止說話，開始辨識 ({len(audio_data)} bytes)...")
                        asyncio.create_task(self.recognize(user, audio_data))

    async def recognize(self, user, pcm_data):
        # 如果音訊過短（小於 0.1 秒），可能是雜訊，忽略不處理
        # 48000Hz * 2 channels * 2 bytes = 192,000 bytes/sec
        if len(pcm_data) < 19000: 
            print(f"忽略過短音訊: {len(pcm_data)} bytes")
            return

        # 1. 儲存原始立體聲 (Stereo) 音訊供除錯
        # 如果這個檔案聽起來也是雜訊，代表是 Discord 接收或解碼的問題 (缺少 Opus 函式庫等)
        try:
            with wave.open(f"debug_raw_{user.name}.wav", "wb") as f:
                f.setnchannels(2) # 立體聲
                f.setsampwidth(2) # 16-bit
                f.setframerate(48000)
                f.writeframes(pcm_data)
        except Exception as e:
            print(f"無法寫入除錯檔案: {e}")

        # 2. 轉為單聲道 (Mono)
        # 改用只取左聲道 (Left Channel)，這是最安全的轉換方式，避免混音造成的爆音
        mono_data = audioop.tomono(pcm_data, 2, 1, 0)

        # 將 48000Hz 降頻至 16000Hz (Speech Recognition 常用頻率，能提高辨識率)
        mono_data, _ = audioop.ratecv(mono_data, 2, 1, 48000, 16000, None)
        
        # 3. 建立 AudioData
        # 修正：sample_width 必須是 2 (16-bit)，之前設為 1 導致辨識引擎讀取錯誤
        audio = sr.AudioData(mono_data, 16000, 2)

        try:
            loop = asyncio.get_running_loop()
            # 使用 Google Web Speech API (zh-TW)
            text = await loop.run_in_executor(None, lambda: self.recognizer.recognize_google(audio, language="zh-TW"))
            if text:
                print(f"[{user.name}]: {text}")
                try:
                    async with aiohttp.ClientSession() as session:
                        payload = {'text': text, 'user_name': user.name}
                        async with session.post('http://127.0.0.1:5000/chat', json=payload) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                reply = data.get('reply')
                                if reply:
                                    await self.channel.send(f"**R8 回覆 {user.name}**: {reply}")
                                else:
                                    print(f"LLM Server 回傳錯誤代碼: {resp.status}")
                                    await self.channel.send(f"**R8 錯誤**: 無法取得回應 (Server {resp.status})")
                except Exception as err:
                    print(f"無法連線到 LLM Server: {err}")
        except sr.UnknownValueError:
            print(f"[{user.name}]: (無法辨識)") # 除錯期間開啟，確認有在嘗試辨識
        except Exception as e:
            print(f"辨識錯誤: {e}")

    def cleanup(self):
        self.running = False

@bot.command(name='join', help='讓機器人加入你所在的語音頻道')
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        # 使用 VoiceRecvClient 以支援語音接收
        voice_client = await channel.connect(cls=voice_recv.VoiceRecvClient)
        voice_client.listen(STTSink(ctx.channel))
        await ctx.send(f'已成功加入語音頻道：{channel.name} (STT 功能已開啟)')
    else:
        await ctx.send('你必須先進入一個語音頻道，我才能加入！')

@bot.command(name='leave', help='讓機器人離開語音頻道')
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send('已離開語音頻道。')
    else:
        await ctx.send('我目前不在任何語音頻道中。')

# --- 執行機器人 ---
if __name__ == "__main__":
    # 設定日誌等級為 WARNING，這樣可以隱藏 INFO 類型的雜訊
    logging.getLogger('discord').setLevel(logging.WARNING)
    logging.getLogger('discord.ext.voice_recv').setLevel(logging.WARNING)
    bot.run(BOT_TOKEN)
