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
        if not bot_token or not chat_id: return
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {"chat_id": chat_id, "text": f"<b>{title}</b>\n\n{message}", "parse_mode": "HTML"}
        try: requests.post(url, data=data, timeout=10)
        except: pass
    
    @staticmethod
    def send_pushplus(title, content):
        token = os.getenv("PUSHPLUS_TOKEN")
        if not token: return
        url = "http://www.pushplus.plus/send"
        data = {"token": token, "title": title, "content": content, "template": "html"}
        try: requests.post(url, data=data, timeout=10)
        except: pass

class LoomiClient:
    def __init__(self):
        self.refresh_token = os.getenv("LOOMI_REFRESH_TOKEN")
        self.access_token = None
        self.api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV2cGN6dnd5Z2VscnZ4emZkY2d2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk4OTU3ODUsImV4cCI6MjA2NTQ3MTc4NX0.y7uP6NVj48UAKnMWcB_5LltTVCVFuSeo7xmrCEHlp1I"
        self.headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json;charset=UTF-8",
            "x-client-info": "supabase-js-web/2.57.4"
        }

    def refresh_access_token(self):
        """使用 refresh_token 获取新的 access_token"""
        print("🔄 正在刷新 Access Token...")
        url = "https://auth.loomi.live/auth/v1/token?grant_type=refresh_token"
        payload = {"refresh_token": self.refresh_token}
        
        try:
            resp = requests.post(url, headers=self.headers, json=payload, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                self.access_token = data.get("access_token")
                # 更新全局 Header
                self.headers["Authorization"] = f"Bearer {self.access_token}"
                print("✅ Token 刷新成功")
                return True
            else:
                print(f"❌ 刷新失败: {resp.text}")
                return False
        except Exception as e:
            print(f"❌ 刷新异常: {e}")
            return False

    def check_in(self, user_id):
        print("🔄 正在执行每日签到...")
        checkin_url = "https://auth.loomi.live/rest/v1/rpc/handle_daily_login_reward"
        payload = {"user_uuid": user_id}
        try:
            resp = requests.post(checkin_url, headers=self.headers, json=payload, timeout=15)
            if resp.status_code in [200, 201, 204]:
                return "✅ 成功领取"
            else:
                msg = resp.json().get('message', '')
                if "already" in msg: return "今日已签"
                return f"未增加 ({msg})"
        except: return "签到异常"

    def run(self):
        if not self.refresh_token:
            print("❌ 错误: 未配置 LOOMI_REFRESH_TOKEN。请参考说明获取并存入 Secrets。")
            return

        # 1. 第一步必须是刷新 Token
        if not self.refresh_access_token():
            LoomiNotifier.send_telegram("Loomi 脚本故障", "❌ Refresh Token 可能已失效，请重新抓取。")
            return

        try:
            # 2. 获取用户信息
            user_resp = requests.get("https://auth.loomi.live/auth/v1/user", headers=self.headers, timeout=15)
            user_data = user_resp.json()
            user_id = user_data.get('id')
            email = user_data.get('email', 'Unknown')
            print(f"👤 当前用户: {email}")

            # 3. 签到
            checkin_res = self.check_in(user_id)

            # 4. 查询余额
            credit_url = f"https://auth.loomi.live/rest/v1/user_credits?user_id=eq.{user_id}&select=*"
            credit_resp = requests.get(credit_url, headers=self.headers, timeout=15)
            balance = 0
            if credit_resp.status_code == 200:
                c_data = credit_resp.json()
                if c_data: balance = c_data[0].get('credits', 0)

            # 5. 发送报告
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            report = f"📅 时间: {now}\n👤 账号: {email}\n📝 签到: {checkin_res}\n💰 余额: {balance}"
            print("\n" + report)
            LoomiNotifier.send_telegram("Loomi 签到提醒", report)
            LoomiNotifier.send_pushplus("Loomi 签到提醒", report)

        except Exception as e:
            print(f"❌ 运行异常: {e}")

if __name__ == "__main__":
    LoomiClient().run()
