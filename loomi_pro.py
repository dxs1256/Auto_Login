import requests
import os
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def get_loomi_credits():
    email = os.getenv("LOOMI_EMAIL")
    password = os.getenv("LOOMI_PASSWORD")
    
    # 从你的HAR文件 - 正确API Key
    api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV2cGN6dnd5Z2VscnZ4emZkY2d2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk4OTU3ODUsImV4cCI6MjA2NTQ3MTc4NX0.y7uP6NVj48UAKnMWcB_5LltTVCVFuSeo7xmrCEHlp1I"
    
    # 1️⃣ 登录
    login_headers = {
        "apikey": api_key,
        "Content-Type": "application/json;charset=UTF-8",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://loomi.live",
        "Referer": "https://loomi.live/"
    }
    
    login_resp = requests.post(
        "https://auth.loomi.live/auth/v1/token?grant_type=password",
        json={"email": email, "password": password},
        headers=login_headers,
        timeout=15
    )
    
    if login_resp.status_code != 200:
        print(f"❌ 登录失败: {login_resp.status_code}")
        print(login_resp.text)
        return
    
    tokens = login_resp.json()
    access_token = tokens["access_token"]
    logger.info("✅ 登录成功")
    
    # 2️⃣ 获取积分（带token）
    api_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    credits_resp = requests.get(
        "https://api.loomi.chat/api/v1/payment/subscription/status",
        headers=api_headers,
        timeout=15
    )
    
    logger.info(f"积分API状态: {credits_resp.status_code}")
    logger.info(f"积分响应: {credits_resp.text[:500]}")
    
    if credits_resp.status_code == 200:
        data = credits_resp.json()
        
        # 精确解析你的4,050积分
        available = 0
        total = 0
        
        # 从HAR文件已知结构
        if data.get('success') and data['data']:
            credits = data['data'].get('credits', {})
            available = credits.get('available', 0)
            total = credits.get('total', 0)
        else:
            # 直接字段
            available = data.get('available', 0) or data.get('credits', {}).get('available', 0)
            total = data.get('total', 0) or data.get('credits', {}).get('total', 0)
        
        result = f"""
🎯 积分概览 (https://v2.loomi.live/zh/profile#user) 
━━━━━━━━━━━━━━━━━━━━━━
💰 可用积分: {available:,}  ← 你页面显示的4,050
💎 总积分:   {total:,}

📅 获取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📧 账号:     {email}
━━━━━━━━━━━━━━━━━━━━━━
        """
        
        print(result)
        
        # 保存
        with open("credits_report.txt", "w", encoding="utf-8") as f:
            f.write(result + "\n\n原始数据:\n" + json.dumps(data, indent=2, ensure_ascii=False))
        
        logger.info(f"🎉 积分获取成功: {available}/{total}")
        return True
    else:
        print(f"❌ 积分获取失败: {credits_resp.status_code}")
        print(credits_resp.text)
        return False

if __name__ == "__main__":
    if os.getenv('GITHUB_ACTIONS'):
        success = get_loomi_credits()
        exit(0 if success else 1)
    else:
        get_loomi_credits()
