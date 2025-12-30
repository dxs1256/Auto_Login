import requests
import json
import os
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
import schedule

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('loomi.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class LoomiAuthManager:
    def __init__(self, config_path: str = "config.json"):
        self.config = self.load_config(config_path)
        self.api_key = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV2cGN6dnd5Z2VscnZ4emZkY2d2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk4OTU3ODUsImV4cCI6MjA2NTQ3MTc4NX0."
            "y7uP6NVj48UAKnMWcB5LltTVCVFuSeo7xmrCEHlp1I"
        )
        self.session = requests.Session()
        self.tokens_file = "tokens.json"
        self.refresh_token = ""
        self.expires_at = None
        self.load_tokens()

    def load_config(self, path: str) -> Dict:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # GitHub Actions 临时配置
            config = {
                "accounts": [{"name": "Actions", "email": os.getenv("LOOMI_EMAIL"), "password": os.getenv("LOOMI_PASSWORD")}],
                "settings": {"auto_refresh": True, "retry_times": 3}
            }
            logger.info("使用环境变量配置")
            return config

    def save_tokens(self):
        token_data = {
            "last_update": datetime.now().isoformat(),
            "access_token": self.session.headers.get("Authorization", "").replace("Bearer ", ""),
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at.isoformat() if self.expires_at else ""
        }
        with open(self.tokens_file, 'w') as f:
            json.dump(token_data, f, indent=2)
        logger.info("Token已保存")

    def load_tokens(self):
        if os.path.exists(self.tokens_file):
            with open(self.tokens_file, 'r') as f:
                data = json.load(f)
                self.session.headers.update({
                    "Authorization": f"Bearer {data['access_token']}",
                    "apikey": self.api_key,
                    "Content-Type": "application/json"
                })
                self.refresh_token = data.get('refresh_token', '')
                expires_str = data.get('expires_at', '')
                if expires_str:
                    self.expires_at = datetime.fromisoformat(expires_str)
                logger.info("已加载本地Token")

    def login(self, email: str, password: str, retry: int = 0) -> bool:
        try:
            url = "https://auth.loomi.live/auth/v1/token"
            params = {"grant_type": "password"}
            payload = {"email": email, "password": password}
            
            resp = requests.post(url, params=params, json=payload, 
                               headers={"apikey": self.api_key, "Content-Type": "application/json"},
                               timeout=10)
            resp.raise_for_status()
            
            data = resp.json()
            access_token = data["access_token"]
            self.refresh_token = data["refresh_token"]
            self.expires_at = datetime.now() + timedelta(seconds=data["expires_in"])
            
            self.session.headers.update({
                "Authorization": f"Bearer {access_token}",
                "apikey": self.api_key,
                "Content-Type": "application/json"
            })
            self.save_tokens()
            logger.info(f"✅ 登录成功: {email}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 登录失败 (重试{retry}): {e}")
            if retry < 3:
                time.sleep(2 ** retry)
                return self.login(email, password, retry + 1)
            return False

    def refresh(self) -> bool:
        try:
            url = "https://auth.loomi.live/auth/v1/token"
            params = {"grant_type": "refresh_token"}
            payload = {"refresh_token": self.refresh_token}
            
            resp = requests.post(url, params=params, json=payload,
                               headers={"apikey": self.api_key, "Content-Type": "application/json"},
                               timeout=10)
            resp.raise_for_status()
            
            data = resp.json()
            access_token = data["access_token"]
            self.refresh_token = data.get("refresh_token", self.refresh_token)
            self.expires_at = datetime.now() + timedelta(seconds=data["expires_in"])
            
            self.session.headers["Authorization"] = f"Bearer {access_token}"
            self.save_tokens()
            logger.info("✅ Token刷新成功")
            return True
        except Exception as e:
            logger.error(f"❌ 刷新失败: {e}")
            return False

    def ensure_auth(self) -> bool:
        if not self.refresh_token:
            account = self.config["accounts"][0]
            return self.login(account["email"], account["password"])
        
        if self.expires_at and datetime.now() >= self.expires_at - timedelta(minutes=5):
            return self.refresh()
        return True

    def api_call(self, method: str, url: str, **kwargs) -> requests.Response:
        if not self.ensure_auth():
            raise Exception("认证失败")
        
        resp = self.session.request(method, url, **kwargs)
        if resp.status_code == 401:
            if self.ensure_auth():
                resp = self.session.request(method, url, **kwargs)
        return resp

def github_actions_signin():
    """GitHub Actions专用签到函数"""
    manager = LoomiAuthManager()
    
    if manager.ensure_auth():
        # 签到核心：查询订阅状态
        try:
            resp = manager.api_call("GET", "https://api.loomi.chat/api/v1/payment/subscription/status")
            print(f"✅ 订阅状态: {resp.status_code}")
            print(f"📊 数据: {resp.text[:200]}...")
            
            # 查询信用记录
            resp2 = manager.api_call("GET", "https://auth.loomi.live/rest/v1/credit_transactions", 
                                   params={"user_id": "eq.e987ba3a-9a4a-4bf9-8966-cd4dcfc18b8f", "limit": 10})
            credits = resp2.json()
            print(f"💰 信用记录: {len(credits)} 条")
            
            print("🎉 Loomi每日签到完成！")
            logger.info("🎉 GitHub Actions签到成功")
            return True
        except Exception as e:
            print(f"❌ API调用失败: {e}")
            logger.error(f"❌ API调用失败: {e}")
            return False
    else:
        print("❌ 登录失败")
        return False

if __name__ == "__main__":
    # GitHub Actions 自动检测
    if os.getenv('GITHUB_ACTIONS') == 'true' or os.getenv('GITHUB_RUN_ID'):
        github_actions_signin()
    else:
        print("=== Loomi Pro 本地版 ===")
        print("1. 测试签到  2. 手动登录")
        choice = input("选择: ")
        if choice == "1":
            github_actions_signin()
