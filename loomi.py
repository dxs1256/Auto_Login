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
        data = {
            "chat_id": chat_id,
            "text": f"<b>{title}</b>\n\n{message}",
            "parse_mode": "HTML"
        }
        try:
            requests.post(url, data=data, timeout=10)
        except:
            pass
    
    @staticmethod
    def send_pushplus(title, content):
        token = os.getenv("PUSHPLUS_TOKEN")
        if not token:
            return
        url = "http://www.pushplus.plus/send"
        data = {"token": token, "title": title, "content": content, "template": "html"}
        try:
            requests.post(url, data=data, timeout=10)
        except:
            pass

class LoomiClient:
    def __init__(self):
        self.token = os.getenv("LOOMI_TOKEN")
        # 固定配置 (来自抓包)
        self.api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV2cGN6dnd5Z2VscnZ4emZkY2d2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk4OTU3ODUsImV4cCI6MjA2NTQ3MTc4NX0.y7uP6NVj48UAKnMWcB_5LltTVCVFuSeo7xmrCEHlp1I"
        self.headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "x-client-info": "supabase-js-web/2.50.0"
        }

    def run(self):
        if not self.token:
            print("❌ 错误：环境变量 LOOMI_TOKEN 未设置")
            return

        print("🔄 正在连接 Loomi...")
        
        email = "未知用户"
        credits = 0
        status_msg = "初始化"

        try:
            # 1. 获取 User ID (必须步骤)
            user_url = "https://auth.loomi.live/auth/v1/user"
            user_resp = requests.get(user_url, headers=self.headers, timeout=15)
            
            if user_resp.status_code == 200:
                user_data = user_resp.json()
                user_id = user_data.get('id')
                email = user_data.get('email', email)
                print(f"✅ 认证成功: {email}")
                
                # 2. 使用 p_user_id 获取积分 (关键步骤)
                rpc_url = "https://auth.loomi.live/rest/v1/rpc/get_user_current_credits"
                payload = {
                    "p_user_id": user_id  # <--- 这里就是我们要修复的关键参数
                }
                
                # RPC 必须用 POST
                credit_resp = requests.post(rpc_url, headers=self.headers, json=payload, timeout=15)
                
                if credit_resp.status_code == 200:
                    credits = credit_resp.json()
                    status_msg = "🟢 数据获取成功"
                    print(f"💰 当前真实积分: {credits}")
                else:
                    status_msg = f"🔴 积分接口错误 {credit_resp.status_code}"
                    print(f"❌ 获取积分失败: {credit_resp.text}")
            else:
                status_msg = f"🔴 Token无效或过期 ({user_resp.status_code})"
                print("❌ 无法获取用户信息，请检查 LOOMI_TOKEN 是否过期")

        except Exception as e:
            status_msg = f"🔴 脚本执行出错: {str(e)}"
            print(status_msg)

        # 3. 发送通知
        now_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        msg = f"""
📅 <b>时间</b>: {now_time}
📧 <b>账号</b>: {email}

💰 <b>当前积分</b>: <code>{credits}</code>

📝 <b>状态</b>: {status_msg}
        """
        
        # 保存报告文件 (供 GitHub Actions 下载)
        with open("credits_report.txt", "w", encoding="utf-8") as f:
            f.write(msg)
            
        notifier = LoomiNotifier()
        notifier.send_telegram("Loomi 每日统计", msg)
        notifier.send_pushplus("Loomi 每日统计", msg)
        print("\n✅ 任务完成")

if __name__ == "__main__":
    LoomiClient().run()
