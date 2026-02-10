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
        # 从环境变量获取刷新令牌
        self.refresh_token = os.getenv("LOOMI_REFRESH_TOKEN")
        self.access_token = None
        # 这是 Loomi 的固定 API Key
        self.api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV2cGN6dnd5Z2VscnZ4emZkY2d2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk4OTU3ODUsImV4cCI6MjA2NTQ3MTc4NX0.y7uP6NVj48UAKnMWcB_5LltTVCVFuSeo7xmrCEHlp1I"
        self.headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json;charset=UTF-8",
            "x-client-info": "supabase-js-web/2.57.4"
        }

    def refresh_auth(self):
        """使用 refresh_token 刷新登录状态"""
        print("🔄 正在通过 Refresh Token 续期...")
        url = "https://auth.loomi.live/auth/v1/token?grant_type=refresh_token"
        payload = {"refresh_token": self.refresh_token}
        
        try:
            resp = requests.post(url, headers=self.headers, json=payload, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                self.access_token = data.get("access_token")
                # 更新后续请求的授权头
                self.headers["Authorization"] = f"Bearer {self.access_token}"
                print("✅ Token 续期成功！")
                return True
            else:
                print(f"❌ 续期失败: {resp.text}")
                return False
        except Exception as e:
            print(f"❌ 续期过程发生异常: {e}")
            return False

    def check_in(self, user_id):
        """执行每日签到"""
        print("🔄 正在尝试签到...")
        url = "https://auth.loomi.live/rest/v1/rpc/handle_daily_login_reward"
        payload = {"user_uuid": user_id}
        try:
            resp = requests.post(url, headers=self.headers, json=payload, timeout=15)
            # RPC 接口成功通常返回 200 或 204
            if resp.status_code in [200, 201, 204]:
                return "✅ 签到成功"
            else:
                err_msg = resp.json().get('message', '未知反馈')
                if "already" in err_msg or "Duplicate" in err_msg:
                    return "ℹ️ 今日已签到过"
                return f"❌ 失败: {err_msg}"
        except:
            return "⚠️ 签到请求异常"

    def run(self):
        if not self.refresh_token:
            print("❌ 错误: 环境变量 LOOMI_REFRESH_TOKEN 为空")
            return

        # 1. 刷新 Token (避开验证码的关键步骤)
        if not self.refresh_auth():
            LoomiNotifier.send_telegram("Loomi 脚本故障", "Refresh Token 已过期，请重新手动登录官网抓取。")
            return

        try:
            # 2. 获取用户信息
            user_resp = requests.get("https://auth.loomi.live/auth/v1/user", headers=self.headers, timeout=15)
            user_data = user_resp.json()
            user_id = user_data.get('id')
            email = user_data.get('email', '未知用户')
            print(f"👤 账号: {email}")

            # 3. 签到
            checkin_status = self.check_in(user_id)
            print(f"📝 结果: {checkin_status}")

            # 4. 查询积分余额 (根据你提供的 subscription-store 逻辑)
            balance = "未知"
            credit_url = f"https://auth.loomi.live/rest/v1/user_credits?user_id=eq.{user_id}&select=*"
            credit_resp = requests.get(credit_url, headers=self.headers, timeout=15)
            if credit_resp.status_code == 200:
                c_data = credit_resp.json()
                if c_data:
                    # 优先取 credits，其次取 total_credits
                    balance = c_data[0].get('credits', c_data[0].get('total_credits', 0))

            # 5. 发送通知
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            msg = f"📅 时间: {now}\n👤 账号: {email}\n📝 状态: {checkin_status}\n💰 余额: {balance}"
            print("\n" + msg)
            
            LoomiNotifier.send_telegram("Loomi 每日签到报告", msg)
            LoomiNotifier.send_pushplus("Loomi 每日签到报告", msg)

        except Exception as e:
            print(f"❌ 运行中出错: {e}")

if __name__ == "__main__":
    LoomiClient().run()
