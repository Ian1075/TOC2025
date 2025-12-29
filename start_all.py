import subprocess
import sys
import time
import os

def main():
    # 取得目前檔案所在的資料夾
    cwd = os.path.dirname(os.path.abspath(__file__))
    
    # 定義要執行的檔案
    server_script = os.path.join(cwd, "llm_server.py")
    bot_script = os.path.join(cwd, "bot.py")

    print("=== 正在啟動 TOC2025 整合系統 ===")

    processes = []
    try:
        # 1. 啟動 LLM Server
        print(f"[系統] 正在啟動 LLM Server...")
        # 使用 sys.executable 確保使用同一個 Python 環境執行
        p_server = subprocess.Popen([sys.executable, server_script], cwd=cwd)
        processes.append(p_server)

        # 等待 Server 啟動 (給予 3 秒緩衝時間)
        time.sleep(3)

        # 2. 啟動 Discord Bot
        print(f"[系統] 正在啟動 Discord Bot...")
        p_bot = subprocess.Popen([sys.executable, bot_script], cwd=cwd)
        processes.append(p_bot)

        print("\n=== 服務已全部啟動 ===")
        print("按 Ctrl+C 可以一次關閉所有程式\n")

        # 監控迴圈：如果任一程式崩潰，就結束
        while True:
            time.sleep(1)
            if p_server.poll() is not None:
                print("[錯誤] LLM Server 已意外停止")
                break
            if p_bot.poll() is not None:
                print("[錯誤] Discord Bot 已意外停止")
                break

    except KeyboardInterrupt:
        print("\n[系統] 接收到停止指令...")
    finally:
        print("[系統] 正在關閉所有服務...")
        for p in processes:
            if p.poll() is None:
                p.terminate()
        print("[系統] 已關閉。")

if __name__ == "__main__":
    main()