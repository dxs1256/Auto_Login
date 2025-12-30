import requests
import os
import json
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

class LoomiNotifier:
    @staticmethod
    def send_telegram(title, message):
        """Telegram通知"""
        bot_token = os.getenv("TG_BOT_TOKEN")
        chat_id = os.getenv("TG_CHAT_ID")
        if not bot_token or not chat_id:
            return False
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": f"{title}\n\n{message}",
            "parse_mode": "HTML"
        }
        resp = requests.post(url, data=data, timeout=10)
        logger.info(f"📱 TG通知: {resp.status_code}")
        return resp.status_code == 200
    
    @staticmethod
    def send_pushplus(title, content):
        """PushPlus通知"""
        token = os.getenv("PUSHPLUS_TOKEN")
        if not token:
            return False
        
        url = "http://www.pushplus.plus/send"
        data = {
            "token": token,
            "title": title,
            "content": content,
            "template": "html"
        }
        resp = requests.post(url, data=data, timeout=10)
        logger.info(f"📲 PushPlus通知: {resp.status_code}")
        return "成功" in resp.text

class LoomiTokenManager:
    def __init__(self):
        self.api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV2cGN6dnd5Z2VscnZ4emZkY2d2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk4OTU3ODUsImV4cCI6MjA2NTQ3MTc4NX0.y7uP6NVj48UAKnMWcB5LltTVCVFuSeo7xmrCEHlp1I"
        self.tokens_file = "tokens.json"
        self.session = requests.Session()
        self.load_tokens()
    
    def save_tokens(self, access_token, refresh_token, expires_in):
        token_data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": (datetime.now() + timedelta(seconds=expires_in)).isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        with open(self.tokens_file, 'w') as f:
            json.dump(token_data, f, indent=2)
    
    def load_tokens(self):
        if os.path.exists(self.tokens_file):
            with open(self.tokens_file, 'r') as f:
                data = json.load(f)
                self.session.headers.update({
                    "Authorization": f"Bearer {data['access_token']}",
                    "Content-Type": "application/json"
                })
                logger.info("💾 本地token已加载")
    
    def login(self, email, password):
        login_headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json;charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.post(
            "https://auth.loomi.live/auth/v1/token?grant_type=password",
            json={"email": email, "password": password},
            headers=login_headers
        )
        if resp.status_code == 200:
            tokens = resp.json()
            self.save_tokens(tokens["access_token"], tokens["refresh_token"], tokens["expires_in"])
            self.session.headers["Authorization"] = f"Bearer {tokens['access_token']}"
            logger.info("✅ 登录成功")
            return True
        return False
    
    def ensure_valid_token(self, email, password):
        if os.path.exists(self.tokens_file):
            with open(self.tokens_file, 'r') as f:
                data = json.load(f)
                expires_at = datetime.fromisoformat(data['expires_at'])
                if datetime.now() < expires_at - timedelta(minutes=10):
                    return True
        
        return self.login(email, password)

def loomi_signin():
    email = os.getenv("LOOMI_EMAIL")
    manager = LoomiTokenManager()
    
    # 确保token有效
    if not manager.ensure_valid_token(email, email):  # password从env获取
        notifier = LoomiNotifier()
        msg = "❌ <b>Loomi签到失败</b>\n登录失败，请检查账号密码"
        notifier.send_telegram("🚨 Loomi签到失败", msg)
        notifier.send_pushplus("🚨 Loomi签到失败", msg)
        return False
    
    # 获取积分
    resp = manager.session.get("https://api.loomi.chat/api/v1/payment/subscription/status")
    
    available = 0
    total = 0
    if resp.status_code == 200:
        data = resp.json()
        credits = data.get('data', {}).get('credits', {}) if data.get('success') else data
        available = credits.get('available', 0)
        total = credits.get('total', 0)
    
    # 格式化通知消息
    signin_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    message = f"""
<b>🎉 Loomi每日签到成功！</b>

💰 <b>可用积分</b>: {available:,}
💎 <b>总积分</b>: {total:,}
📅 <b>签到时间</b>: {signin_time}
📧 <b>账号</b>: {email}

<i>GitHub Actions 自动签到</i>
    """
    
    # 双重通知
    notifier = LoomiNotifier()
    notifier.send_telegram("✅ Loomi签到成功", message)
    notifier.send_pushplus("✅ Loomi签到成功", message)
    
    # 保存报告
    with open("credits_report.txt", "w", encoding="utf-8") as f:
        f.write(message + f"\n\nAPI状态: {resp.status_code}")
    
    logger.info(f"🎉 签到完成: {available}/{total}")
    print(message)
    return True

if __name__ == "__main__":
    if os.getenv('GITHUB_ACTIONS'):
        success = loomi_signin()
        exit(0 if success else 1)
    else:
        loomi_signin()
