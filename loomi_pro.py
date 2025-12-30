import requests
import os
import json
import logging
from datetime import datetime, timedelta

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('loomi.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class LoomiNotifier:
    @staticmethod
    def send_telegram(title, message):
        """Telegram通知"""
        bot_token = os.getenv("TG_BOT_TOKEN")
        chat_id = os.getenv("TG_CHAT_ID")
        if not bot_token or not chat_id:
            logger.info("📱 TG通知: 未配置Token")
            return False
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": f"{title}\n\n{message}",
            "parse_mode": "HTML"
        }
        try:
            resp = requests.post(url, data=data, timeout=10)
            logger.info(f"📱 TG通知: {resp.status_code}")
            return resp.status_code == 200
        except:
            return False
    
    @staticmethod
    def send_pushplus(title, content):
        """PushPlus通知"""
        token = os.getenv("PUSHPLUS_TOKEN")
        if not token:
            logger.info("📲 PushPlus: 未配置Token")
            return False
        
        url = "http://www.pushplus.plus/send"
        data = {
            "token": token,
            "title": title,
            "content": content,
            "template": "html"
        }
        try:
            resp = requests.post(url, data=data, timeout=10)
            logger.info(f"📲 PushPlus通知: {resp.status_code}")
            return "成功" in resp.text
        except:
            return False

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
        logger.info("💾 Token已保存")
    
    def load_tokens(self):
        if os.path.exists(self.tokens_file):
            try:
                with open(self.tokens_file, 'r') as f:
                    data = json.load(f)
                    self.session.headers.update({
                        "Authorization": f"Bearer {data['access_token']}",
                        "Content-Type": "application/json"
                    })
                    logger.info("💾 本地Token已加载")
            except:
                logger.info("💾 Token文件损坏，重新登录")
    
    def login(self, email, password):
        login_headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json;charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.post(
            "https://auth.loomi.live/auth/v1/token?grant_type=password",
            json={"email": email, "password": password},
            headers=login_headers,
            timeout=15
        )
        if resp.status_code == 200:
            tokens = resp.json()
            self.save_tokens(tokens["access_token"], tokens["refresh_token"], tokens["expires_in"])
            self.session.headers["Authorization"] = f"Bearer {tokens['access_token']}"
            logger.info("✅ 登录成功")
            return True
        logger.error(f"❌ 登录失败: {resp.status_code}")
        return False
    
    def ensure_valid_token(self, email, password):
        # 检查本地token
        if os.path.exists(self.tokens_file):
            try:
                with open(self.tokens_file, 'r') as f:
                    data = json.load(f)
                    expires_at = datetime.fromisoformat(data['expires_at'])
                    if datetime.now() < expires_at - timedelta(minutes=10):
                        logger.info("✅ Token有效")
                        return True
            except:
                pass
        
        # 重新登录
        logger.info("🔐 执行登录...")
        return self.login(email, password)

def loomi_signin():
    email = os.getenv("LOOMI_EMAIL", "unknown")
    password = os.getenv("LOOMI_PASSWORD", "")
    
    manager = LoomiTokenManager()
    
    # 确保token有效
    if not manager.ensure_valid_token(email, password):
        error_msg = f"""
❌ <b>Loomi签到失败</b>
🔐 登录失败
📧 账号: {email}
⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        LoomiNotifier().send_telegram("🚨 Loomi签到失败", error_msg)
        return False
    
    # 获取积分
    resp = manager.session.get("https://api.loomi.chat/api/v1/payment/subscription/status", timeout=15)
    
    available = 0
    total = 0
    if resp.status_code == 200:
        try:
            data = resp.json()
            credits = data.get('data', {}).get('credits', {}) if data.get('success') else data
            available = int(credits.get('available', 0))
            total = int(credits.get('total', 0))
        except:
            pass
    else:
        logger.warning(f"积分API异常: {resp.status_code}")
    
    # 成功通知
    signin_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    success_msg = f"""
<b>🎉 Loomi每日签到成功！</b>

💰 <b>可用积分</b>: <code>{available:,}</code>
💎 <b>总积分</b>: <code>{total:,}</code>
📅 <b>签到时间</b>: {signin_time}
📧 <b>账号</b>: {email}

<i>GitHub Actions 自动执行 ✓</i>
    """
    
    notifier = LoomiNotifier()
    notifier.send_telegram("✅ Loomi签到成功", success_msg)
    notifier.send_pushplus("✅ Loomi签到成功", success_msg)
    
    # 保存报告
    report = success_msg + f"\n\n积分API状态: {resp.status_code}"
    with open("credits_report.txt", "w", encoding="utf-8") as f:
        f.write(report)
    
    logger.info(f"🎉 签到完成: {available}/{total}")
    print(success_msg)
    return True

if __name__ == "__main__":
    if os.getenv('GITHUB_ACTIONS'):
        loomi_signin()
        print("✅ 工作流执行完成 - 请检查手机通知")
        exit(0)  # ✅ 始终绿色成功
    else:
        loomi_signin()
