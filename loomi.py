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
        # 优先读取账号密码
        self.email = os.getenv("LOOMI_EMAIL")
        self.password = os.getenv("LOOMI_PASSWORD")
        # 手动 Token 作为备用
        self.token = os.getenv("LOOMI_TOKEN")
        
        # 固定配置
        self.api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV2cGN6dnd5Z2VscnZ4emZkY2d2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk4OTU3ODUsImV4cCI6MjA2NTQ3MTc4NX0.y7uP6NVj48UAKnMWcB_5LltTVCVFuSeo7xmrCEHlp1I"
        self.headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json",
            "x-client-info": "supabase-js-web/2.50.0"
        }

    def login(self):
        """尝试使用账号密码获取最新Token"""
        if not self.email or not self.password:
            print("⚠️ 未配置 LOOMI_EMAIL 或 LOOMI_PASSWORD，将使用手动 Token")
            return False

        print(f"🔄 正在尝试自动登录: {self.email}...")
        login_url = "https://auth.loomi.live/auth/v1/token?grant_type=password"
        payload = {
            "email": self.email,
            "password": self.password
        }
        
        try:
            # Supabase 标准登录接口
            resp = requests.post(login_url, headers=self.headers, json=payload, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get("access_token")
                print("✅ 自动登录成功！已获取最新 Token")
                return True
            else:
                print(f"⚠️ 自动登录失败 (代码 {resp.status_code}): {resp.text}")
                print("➡️ 将尝试使用备用 Token (环境变量 LOOMI_TOKEN)")
                return False
        except Exception as e:
            print(f"⚠️ 登录请求异常: {e}")
            return False

    def run(self):
        # 1. 先尝试登录更新 Token
        self.login()
        
        # 2. 检查是否有可用 Token
        if not self.token:
            print("❌ 错误：自动登录失败，且未设置 LOOMI_TOKEN 备用")
            return

        # 更新请求头，加入 Token
        self.headers["Authorization"] = f"Bearer {self.token}"

        print("🔄 正在查询积分...")
        available = 0
        total = 0
        status_msg = "初始化"

        try:
            # 3. 获取用户信息 (为了拿到ID)
            user_url = "https://auth.loomi.live/auth/v1/user"
            user_resp = requests.get(user_url, headers=self.headers, timeout=15)
            
            if user_resp.status_code == 200:
                user_data = user_resp.json()
                user_id = user_data.get('id')
                email_display = user_data.get('email', self.email or "User")
                print(f"✅ 认证成功: {email_display}")
                
                # 4. 获取积分
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
                    status_msg = f"🔴 积分接口错误 {credit_resp.status_code}"
            else:
                status_msg = f"🔴 Token无效 ({user_resp.status_code})"
                if user_resp.status_code == 401:
                    print("💡 提示: 密码可能错误，或手动 Token 已过期")

        except Exception as e:
            status_msg = f"🔴 脚本出错: {str(e)}"
            print(status_msg)

        # 5. 发送通知
        msg = f"""
💰 <b>可用积分</b>: <code>{available}</code>
💎 <b>总计积分</b>: <code>{total}</code>

📝 <b>状态</b>: {status_msg}
        """
        
        with open("credits_report.txt", "w", encoding="utf-8") as f:
            f.write(msg)
            
        notifier = LoomiNotifier()
        notifier.send_telegram("Loomi 每日统计", msg)
        notifier.send_pushplus("Loomi 每日统计", msg)
        print("\n✅ 任务完成")

if __name__ == "__main__":
    LoomiClient().run()
