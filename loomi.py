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

    def refresh_auth(self):
        url = "https://auth.loomi.live/auth/v1/token?grant_type=refresh_token"
        payload = {"refresh_token": self.refresh_token}
        try:
            resp = requests.post(url, headers=self.headers, json=payload, timeout=15)
            if resp.status_code == 200:
                self.access_token = resp.json().get("access_token")
                self.headers["Authorization"] = f"Bearer {self.access_token}"
                return True
            return False
        except: return False

    def check_in(self, user_id):
        url = "https://auth.loomi.live/rest/v1/rpc/handle_daily_login_reward"
        payload = {"user_uuid": user_id}
        try:
            resp = requests.post(url, headers=self.headers, json=payload, timeout=15)
            if resp.status_code in [200, 201, 204]:
                return "✅ 成功领取"
            else:
                msg = resp.json().get('message', '')
                if "already" in msg: return "ℹ️ 今日已签"
                return f"❌ {msg}"
        except: return "⚠️ 异常"

    def run(self):
        if not self.refresh_token:
            print("❌ 未配置 LOOMI_REFRESH_TOKEN")
            return

        if not self.refresh_auth():
            print("❌ Token 刷新失败")
            return

        try:
            # 1. 获取 ID
            user_resp = requests.get("https://auth.loomi.live/auth/v1/user", headers=self.headers, timeout=15)
            user_id = user_resp.json().get('id')
            email = user_resp.json().get('email')

            # 2. 签到
            res = self.check_in(user_id)

            # 3. 查询积分余额 (重点修改部分)
            print("🔍 正在查询详细积分...")
            credit_url = f"https://auth.loomi.live/rest/v1/user_credits?user_id=eq.{user_id}&select=*"
            credit_resp = requests.get(credit_url, headers=self.headers, timeout=15)
            
            available_balance = 0
            if credit_resp.status_code == 200:
                data = credit_resp.json()
                if data:
                    row = data[0]
                    # === 调试打印：如果你发现数值还是错的，请在 GitHub 日志里看这一行的输出 ===
                    print(f"DEBUG - 原始积分数据: {json.dumps(row)}")
                    
                    # 尝试多种取值方式，优先取“可用积分”
                    total = row.get('total_credits', 0)
                    used = row.get('used_credits', 0)
                    
                    # 逻辑 1: 如果有 credits 字段直接用
                    if 'credits' in row:
                        available_balance = row['credits']
                    # 逻辑 2: 如果有 active_credits 直接用
                    elif 'active_credits' in row:
                        available_balance = row['active_credits']
                    # 逻辑 3: 计算得出 (总额 - 已用)
                    else:
                        available_balance = total - used
                else:
                    print("⚠️ 未找到积分行数据")
            else:
                print(f"❌ 积分请求失败: {credit_resp.status_code}")

            # 4. 生成报告
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            report = (
                f"📅 <b>时间</b>: {now}\n"
                f"👤 <b>账号</b>: {email}\n"
                f"📝 <b>签到</b>: {res}\n"
                f"💰 <b>可用余额</b>: <code>{available_balance}</code>"
            )
            print("\n" + report.replace("<b>","").replace("</b>","").replace("<code>","").replace("</code>",""))
            
            LoomiNotifier.send_telegram("Loomi 签到提醒", report)
            LoomiNotifier.send_pushplus("Loomi 签到提醒", report)

        except Exception as e:
            print(f"❌ 运行异常: {e}")

if __name__ == "__main__":
    LoomiClient().run()
