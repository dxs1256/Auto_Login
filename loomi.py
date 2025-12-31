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
        except:
            pass
    
    @staticmethod
    def send_pushplus(title, content):
        token = os.getenv("PUSHPLUS_TOKEN")
        if not token:
            return
        url = "http://www.pushplus.plus/send"
        data = {"token": token, "title": title, "content": content, "template": "html"}
        try:
            requests.post(url, data=data, timeout=10)
        except:
            pass

class LoomiClient:
    def __init__(self):
        self.token = os.getenv("LOOMI_TOKEN")
        self.api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV2cGN6dnd5Z2VscnZ4emZkY2d2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk4OTU3ODUsImV4cCI6MjA2NTQ3MTc4NX0.y7uP6NVj48UAKnMWcB_5LltTVCVFuSeo7xmrCEHlp1I"
        self.headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "x-client-info": "supabase-js-web/2.50.0"
        }

    def run(self):
        if not self.token:
            print("❌ 错误：环境变量 LOOMI_TOKEN 未设置")
            return

        print("🔄 正在连接 Loomi...")
        
        available = 0
        total = 0
        status_msg = "初始化"

        try:
            # 1. 获取用户信息 (为了拿到ID)
            user_url = "https://auth.loomi.live/auth/v1/user"
            user_resp = requests.get(user_url, headers=self.headers, timeout=15)
            
            if user_resp.status_code == 200:
                user_data = user_resp.json()
                user_id = user_data.get('id')
                print(f"✅ 认证成功")
                
                # 2. 获取积分
                rpc_url = "https://auth.loomi.live/rest/v1/rpc/get_user_current_credits"
                payload = {"p_user_id": user_id}
                
                credit_resp = requests.post(rpc_url, headers=self.headers, json=payload, timeout=15)
                
                if credit_resp.status_code == 200:
                    raw_data = credit_resp.json()
                    if isinstance(raw_data, list) and len(raw_data) > 0:
                        data = raw_data[0]
                        available = data.get('available_credits', 0)
                        total = data.get('total_credits', 0)
                        status_msg = "🟢 获取成功"
                        print(f"💰 积分详情: 可用 {available} | 总计 {total}")
                    else:
                        status_msg = "⚠️ 数据格式异常"
                else:
                    status_msg = f"🔴 接口错误 {credit_resp.status_code}"
            else:
                status_msg = f"🔴 Token过期 ({user_resp.status_code})"

        except Exception as e:
            status_msg = f"🔴 脚本出错: {str(e)}"
            print(status_msg)

        # 3. 发送精简版通知
        msg = f"""
💰 <b>可用积分</b>: <code>{available}</code>
💎 <b>总计积分</b>: <code>{total}</code>

📝 <b>状态</b>: {status_msg}
        """
        
        # 写入报告
        with open("credits_report.txt", "w", encoding="utf-8") as f:
            f.write(msg)
            
        notifier = LoomiNotifier()
        notifier.send_telegram("Loomi 每日统计", msg)
        notifier.send_pushplus("Loomi 每日统计", msg)
        print("\n✅ 任务完成")

if __name__ == "__main__":
    LoomiClient().run()
