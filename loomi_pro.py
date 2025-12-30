import requests
import json
import os
import time
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

class LoomiAuthManager:
    def __init__(self):
        self.api_key = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV2cGN6dnd5Z2VscnZ4emZkY2d2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk4OTU3ODUsImV4cCI6MjA2NTQ3MTc4NX0."
            "y7uP6NVj48UAKnMWcB5LltTVCVFuSeo7xmrCEHlp1I"
        )
        self.session = requests.Session()

    def test_login(self):
        """精确复现HAR请求"""
        email = os.getenv("LOOMI_EMAIL")
        password = os.getenv("LOOMI_PASSWORD")
        
        print(f"🔍 调试信息:")
        print(f"   邮箱: {repr(email)} (长度:{len(email)})")
        print(f"   密码: {repr(password)} (长度:{len(password)})")
        
        # HAR精确复现
        url = "https://auth.loomi.live/auth/v1/token"
        params = {"grant_type": "password"}
        headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json; charset=UTF-8",  # HAR关键！
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*",
            "Origin": "https://loomi.live",
            "Referer": "https://loomi.live/",
        }
        payload = {
            "email": email,
            "password": password,
            "gotrue_meta_security": {}  # HAR中有这个！
        }
        
        print(f"📤 发送请求: POST {url}")
        print(f"📋 Headers: {headers}")
        print(f"📦 Payload: {json.dumps(payload, indent=2)}")
        
        resp = requests.post(url, params=params, json=payload, headers=headers, timeout=15)
        
        print(f"📥 响应: {resp.status_code}")
        print(f"📋 响应头: {dict(resp.headers)}")
        print(f"📦 响应体: {resp.text[:1000]}")
        
        if resp.status_code == 200:
            print("🎉 登录成功！")
            data = resp.json()
            print(f"✅ Token: {data.get('access_token', '获取成功')[:50]}...")
            return True
        else:
            print("❌ 登录失败")
            return False

    def signin(self):
        """签到流程"""
        if self.test_login():
            # 测试API调用
            self.session.headers.update({
                "Authorization": f"Bearer {resp.json()['access_token']}",
                "apikey": self.api_key,
                "Content-Type": "application/json"
            })
            sub_resp = self.session.get("https://api.loomi.chat/api/v1/payment/subscription/status")
            print(f"✅ 订阅状态: {sub_resp.status_code}")
            print("🎉 签到完成！")
        else:
            print("❌ 签到失败")

if __name__ == "__main__":
    if os.getenv('GITHUB_ACTIONS'):
        LoomiAuthManager().test_login()
