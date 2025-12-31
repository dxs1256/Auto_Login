import requests
import os
import logging
import json
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

class LoomiClient:
    def __init__(self):
        # 从环境变量获取 Token (Bearer 后面那一大串)
        self.token = os.getenv("LOOMI_TOKEN")
        
        # 这是从你提供的抓包数据中提取的固定配置
        self.project_ref = "evpczvwygelrvxzfdcgv"
        self.api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV2cGN6dnd5Z2VscnZ4emZkY2d2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk4OTU3ODUsImV4cCI6MjA2NTQ3MTc4NX0.y7uP6NVj48UAKnMWcB_5LltTVCVFuSeo7xmrCEHlp1I"
        
        # 构造请求头
        self.headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "x-client-info": "supabase-js-web/2.50.0"
        }

    def get_real_data(self):
        if not self.token:
            print("❌ 错误：未设置 LOOMI_TOKEN 环境变量")
            return

        print("🔄 正在连接 Loomi (Supabase)...")

        # 1. 获取用户基础信息 (为了拿到 User ID)
        user_url = "https://auth.loomi.live/auth/v1/user"
        try:
            resp = requests.get(user_url, headers=self.headers, timeout=10)
            if resp.status_code != 200:
                print(f"❌ Token可能已过期，状态码: {resp.status_code}")
                return
            
            user_data = resp.json()
            user_id = user_data.get('id')
            email = user_data.get('email')
            print(f"👤 用户认证成功: {email} (ID: {user_id})")

        except Exception as e:
            print(f"❌ 连接认证服务器失败: {e}")
            return

        # 2. 尝试从数据库获取积分
        # Supabase 的标准数据查询接口是 /rest/v1/表名
        # 我们猜测表名为 'profiles' (这是 Supabase 最常见的用户信息表名)
        db_url = f"https://{self.project_ref}.supabase.co/rest/v1/profiles?select=*"
        
        try:
            # 请求数据库
            db_resp = requests.get(db_url, headers=self.headers, timeout=10)
            
            if db_resp.status_code == 200:
                profiles = db_resp.json()
                if profiles and len(profiles) > 0:
                    profile = profiles[0]
                    
                    # --- 自动寻找积分字段 ---
                    # 常见的积分字段名：credits, points, balance, token
                    credits = profile.get('credits') or profile.get('points') or profile.get('balance') or 0
                    
                    # 打印结果
                    print("\n" + "="*30)
                    print(f"💰 真实积分: {credits}")
                    print(f"📊 完整数据: {json.dumps(profile, ensure_ascii=False)}")
                    print("="*30 + "\n")
                    
                    # 这里你可以添加发送通知的逻辑
                else:
                    print("⚠️ 获取到了 profiles 表，但数据为空。可能表名不对。")
            else:
                print(f"⚠️ 无法读取 profiles 表 (状态码 {db_resp.status_code})")
                print("可能是表名不是 'profiles'，或者权限不足。")
                
        except Exception as e:
            print(f"❌ 查询数据库失败: {e}")

if __name__ == "__main__":
    client = LoomiClient()
    client.get_real_data()
