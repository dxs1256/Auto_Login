import requests
import os
import json
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

class LoomiTokenManager:
    def __init__(self):
        self.api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV2cGN6dnd5Z2VscnZ4emZkY2d2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk4OTU3ODUsImV4cCI6MjA2NTQ3MTc4NX0.y7uP6NVj48UAKnMWcB_5LltTVCVFuSeo7xmrCEHlp1I"
        self.tokens_file = "tokens.json"
        self.session = requests.Session()
        self.load_tokens()
    
    def save_tokens(self, access_token, refresh_token, expires_in):
        """保存token到文件"""
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
        """加载本地token"""
        if os.path.exists(self.tokens_file):
            with open(self.tokens_file, 'r') as f:
                data = json.load(f)
                self.session.headers.update({
                    "Authorization": f"Bearer {data['access_token']}",
                    "Content-Type": "application/json"
                })
                logger.info("💾 已加载本地token")
    
    def login(self, email, password):
        """登录获取新token"""
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
            self.save_tokens(
                tokens["access_token"], 
                tokens["refresh_token"], 
                tokens["expires_in"]
            )
            self.session.headers["Authorization"] = f"Bearer {tokens['access_token']}"
            logger.info("✅ 登录成功")
            return True
        logger.error(f"❌ 登录失败: {resp.text}")
        return False
    
    def refresh_token(self):
        """自动刷新token"""
        if not hasattr(self, '_refresh_token'):
            return False
        
        refresh_headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json;charset=UTF-8"
        }
        
        resp = requests.post(
            "https://auth.loomi.live/auth/v1/token?grant_type=refresh_token",
            json={"refresh_token": self._refresh_token},
            headers=refresh_headers
        )
        
        if resp.status_code == 200:
            tokens = resp.json()
            self.save_tokens(
                tokens["access_token"],
                tokens.get("refresh_token", self._refresh_token),
                tokens["expires_in"]
            )
            self.session.headers["Authorization"] = f"Bearer {tokens['access_token']}"
            logger.info("🔄 Token刷新成功")
            return True
        logger.error("❌ Token刷新失败")
        return False
    
    def ensure_valid_token(self, email, password):
        """确保token有效（自动登录/刷新）"""
        # 检查本地token是否过期
        if os.path.exists(self.tokens_file):
            with open(self.tokens_file, 'r') as f:
                data = json.load(f)
                expires_at = datetime.fromisoformat(data['expires_at'])
                if datetime.now() < expires_at - timedelta(minutes=10):  # 提前10分钟刷新
                    logger.info("✅ Token有效")
                    return True
        
        # 尝试刷新
        if self.refresh_token():
            return True
        
        # 重新登录
        logger.info("🔐 重新登录...")
        return self.login(email, password)
    
    def get_credits(self):
        """获取积分"""
        resp = self.session.get("https://api.loomi.chat/api/v1/payment/subscription/status")
        logger.info(f"积分API: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            credits = data.get('data', {}).get('credits', {}) if data.get('success') else data
            
            available = credits.get('available', 0)
            total = credits.get('total', 0)
            
            return available, total, data
        return 0, 0, None

def loomi_signin():
    email = os.getenv("LOOMI_EMAIL")
    password = os.getenv("LOOMI_PASSWORD")
    
    manager = LoomiTokenManager()
    
    # 确保token有效
    if not manager.ensure_valid_token(email, password):
        print("❌ Token管理失败")
        return False
    
    # 获取积分
    available, total, raw_data = manager.get_credits()
    
    result = f"""
🎯 积分概览 (v2.loomi.live/zh/profile#user)
━━━━━━━━━━━━━━━━━━━━━━
💰 可用积分: {available:,}
💎 总积分:   {total:,}

📅 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📧 账号: {email}
💾 Token状态: 已自动管理
━━━━━━━━━━━━━━━━━━━━━━
    """
    
    print(result)
    
    # 保存完整报告
    report = result + f"\n\n原始数据:\n{json.dumps(raw_data, indent=2, ensure_ascii=False) if raw_data else '无数据'}"
    with open("credits_report.txt", "w", encoding="utf-8") as f:
        f.write(report)
    
    logger.info(f"🎉 签到完成: {available}/{total}")
    return True

if __name__ == "__main__":
    if os.getenv('GITHUB_ACTIONS'):
        success = loomi_signin()
        exit(0 if success else 1)
    else:
        loomi_signin()
