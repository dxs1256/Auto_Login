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
        self.email = os.getenv("LOOMI_EMAIL")
        self.password = os.getenv("LOOMI_PASSWORD")
        self.token = os.getenv("LOOMI_TOKEN")
        
        # 这里的 API Key 是从你抓包中提取的匿名 Key
        self.api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV2cGN6dnd5Z2VscnZ4emZkY2d2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk4OTU3ODUsImV4cCI6MjA2NTQ3MTc4NX0.y7uP6NVj48UAKnMWcB_5LltTVCVFuSeo7xmrCEHlp1I"
        self.headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json;charset=UTF-8",
            "x-client-info": "supabase-js-web/2.57.4"
        }

    def login(self):
        """登录获取 Access Token"""
        if not self.email or not self.password:
            print("⚠️ 未配置 LOOMI_EMAIL 或 LOOMI_PASSWORD，尝试使用手动 Token")
            return False

        print(f"🔄 正在尝试登录: {self.email}...")
        login_url = "https://auth.loomi.live/auth/v1/token?grant_type=password"
        payload = {"email": self.email, "password": self.password}
        
        try:
            resp = requests.post(login_url, headers=self.headers, json=payload, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get("access_token")
                print("✅ 登录成功！")
                return True
            else:
                print(f"❌ 登录失败: {resp.text}")
                return False
        except Exception as e:
            print(f"❌ 登录异常: {e}")
            return False

    def check_in(self, user_id):
        """执行每日签到 RPC"""
        print("🔄 正在执行每日签到...")
        # 根据 JS 代码，RPC 调用路径通常如下
        checkin_url = "https://auth.loomi.live/rest/v1/rpc/handle_daily_login_reward"
        payload = {"user_uuid": user_id}
        
        try:
            # 签到接口通常需要 Authorization 头
            self.headers["Authorization"] = f"Bearer {self.token}"
            resp = requests.post(checkin_url, headers=self.headers, json=payload, timeout=15)
            
            if resp.status_code in [200, 201, 204]:
                print("✅ 签到操作成功！")
                return "成功领取"
            else:
                # 常见错误：今日已签到
                error_msg = resp.json().get('message', '未知错误')
                print(f"ℹ️ 签到反馈: {error_msg}")
                return f"未增加 ({error_msg})"
        except Exception as e:
            print(f"❌ 签到过程出错: {e}")
            return "签到异常"

    def run(self):
        # 1. 登录
        if not self.login() and not self.token:
            print("❌ 无有效 Token，脚本终止")
            return

        self.headers["Authorization"] = f"Bearer {self.token}"

        checkin_status = "未执行"
        available = 0
        status_msg = "未知"

        try:
            # 2. 获取 User ID (这是签到 RPC 必须的参数)
            user_resp = requests.get("https://auth.loomi.live/auth/v1/user", headers=self.headers, timeout=15)
            if user_resp.status_code != 200:
                print("❌ 获取用户信息失败，Token 可能无效")
                return
            
            user_data = user_resp.json()
            user_id = user_data.get('id')
            email_display = user_data.get('email', "User")
            print(f"👤 当前用户: {email_display}")

            # 3. 执行签到
            checkin_status = self.check_in(user_id)

            # 4. 查询最终积分 (使用之前日志里看到的查询方式)
            # 这里尝试你代码里的 get_user_current_credits，如果失效可以换成查询 user_credits 表
            print("🔄 正在查询积分余额...")
            # 备选方案：直接从 user_credits 表查询
            credit_url = f"https://auth.loomi.live/rest/v1/user_credits?user_id=eq.{user_id}&select=*"
            credit_resp = requests.get(credit_url, headers=self.headers, timeout=15)
            
            if credit_resp.status_code == 200:
                credits_data = credit_resp.json()
                if credits_data:
                    available = credits_data[0].get('total_credits', 0) # 或者是 available_credits
                    status_msg = "🟢 正常"
                else:
                    status_msg = "⚠️ 找不到积分记录"
            else:
                status_msg = f"🔴 查询失败({credit_resp.status_code})"

        except Exception as e:
            status_msg = f"🔴 运行异常: {str(e)}"
            print(status_msg)

        # 5. 生成报告并发送通知
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"""
📅 <b>时间</b>: <code>{now}</code>
👤 <b>账号</b>: <code>{self.email or 'Token模式'}</code>
📝 <b>签到状态</b>: <b>{checkin_status}</b>
💰 <b>当前积分</b>: <code>{available}</code>
📊 <b>系统状态</b>: {status_msg}
        """
        
        print("\n" + msg)
        
        notifier = LoomiNotifier()
        notifier.send_telegram("Loomi 签到提醒", msg)
        notifier.send_pushplus("Loomi 签到提醒", msg)

if __name__ == "__main__":
    LoomiClient().run()
