import requests
import os
import logging
import json
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

class LoomiNotifier:
    @staticmethod
    def send_telegram(title, message):
        bot_token = os.getenv("TG_BOT_TOKEN")
        chat_id = os.getenv("TG_CHAT_ID")
        if not bot_token or not chat_id:
            return
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": f"<b>{title}</b>\n\n{message}",
            "parse_mode": "HTML"
        }
        try:
            requests.post(url, data=data, timeout=10)
        except Exception as e:
            print(f"TG推送失败: {e}")
    
    @staticmethod
    def send_pushplus(title, content):
        token = os.getenv("PUSHPLUS_TOKEN")
        if not token:
            return
        url = "http://www.pushplus.plus/send"
        data = {"token": token, "title": title, "content": content, "template": "html"}
        try:
            requests.post(url, data=data, timeout=10)
        except Exception as e:
            print(f"PushPlus推送失败: {e}")

class LoomiClient:
    def __init__(self):
        self.token = os.getenv("LOOMI_TOKEN")
        # 你的 Project Ref 和 API Key (来自抓包)
        self.api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV2cGN6dnd5Z2VscnZ4emZkY2d2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk4OTU3ODUsImV4cCI6MjA2NTQ3MTc4NX0.y7uP6NVj48UAKnMWcB_5LltTVCVFuSeo7xmrCEHlp1I"
        
        self.headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            # 伪装成网页客户端
            "x-client-info": "supabase-js-web/2.50.0"
        }

    def run(self):
        if not self.token:
            print("❌ 错误：未设置 LOOMI_TOKEN 环境变量")
            return

        print("🔄 正在执行 Loomi 任务...")
        
        current_credits = 0
        email = os.getenv("LOOMI_EMAIL", "User")
        status_msg = ""

        # --- 1. 调用 RPC 获取真实积分 ---
        # RPC调用通常使用 POST 方法，即使是获取数据
        rpc_url = "https://auth.loomi.live/rest/v1/rpc/get_user_current_credits"
        
        try:
            # Body 为空 JSON，因为这个函数不需要参数，它会从 Token 里自动识别用户
            resp = requests.post(rpc_url, headers=self.headers, json={}, timeout=15)
            
            if resp.status_code == 200:
                # 成功！返回的应该直接是个数字，或者包含数字的 json
                try:
                    current_credits = resp.json()
                    status_msg = "🟢 积分获取成功"
                    print(f"💰 当前真实积分: {current_credits}")
                except:
                    # 万一返回的是纯文本
                    current_credits = resp.text
                    status_msg = "🟢 积分数据(文本): " + str(current_credits)
            else:
                status_msg = f"🔴 获取积分失败 (Code: {resp.status_code})"
                print(f"❌ 接口错误: {resp.text}")

        except Exception as e:
            status_msg = f"🔴 网络异常: {str(e)}"
            print(status_msg)

        # --- 2. 发送通知 ---
        now_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        msg = f"""
📅 <b>时间</b>: {now_time}
👤 <b>用户</b>: {email}

💰 <b>当前积分</b>: <code>{current_credits}</code>

📝 <b>状态</b>: {status_msg}
        """
        
        print("\n" + "-"*20)
        print(msg)
        print("-" * 20)
        
        notifier = LoomiNotifier()
        notifier.send_telegram("Loomi 积分日报", msg)
        notifier.send_pushplus("Loomi 积分日报", msg)

if __name__ == "__main__":
    client = LoomiClient()
    client.run()
