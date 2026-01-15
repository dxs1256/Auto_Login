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
        checkin_url = "https://auth.loomi.live/rest/v1/rpc/handle_daily_login_reward"
        payload = {"user_uuid": user_id}
        
        try:
            self.headers["Authorization"] = f"Bearer {self.token}"
            resp = requests.post(checkin_url, headers=self.headers, json=payload, timeout=15)
            
            if resp.status_code in [200, 201, 204]:
                print("✅ 签到操作成功！")
                return "成功领取"
            else:
                error_msg = resp.json().get('message', '未知错误')
                # 有些系统如果是重复签到，会返回特定错误，这里视为今日已完成
                if "already" in error_msg or "Duplicate" in error_msg: 
                    return "今日已签"
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
            # 2. 获取 User ID
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

            # 4. 查询积分 (关键修改部分)
            print("🔄 正在查询积分余额...")
            credit_url = f"https://auth.loomi.live/rest/v1/user_credits?user_id=eq.{user_id}&select=*"
            credit_resp = requests.get(credit_url, headers=self.headers, timeout=15)
            
            if credit_resp.status_code == 200:
                credits_data = credit_resp.json()
                if credits_data:
                    data_row = credits_data[0]
                    
                    # === 🛠️ 调试：打印所有字段，帮你找到正确的余额字段 ===
                    print(f"\n🔍 [调试] API 返回的完整积分数据: {json.dumps(data_row, indent=2)}")
                    
                    # 尝试优先读取 'credits' (通常是余额)，其次读取 'monthly_credits'，最后才是 'total_credits'
                    if 'credits' in data_row:
                        available = data_row['credits']
                        print("👉 采用了 'credits' 字段作为余额")
                    elif 'plan_credits' in data_row and 'purchased_credits' in data_row:
                        # 某些系统余额 = 套餐积分 + 购买积分
                         available = data_row.get('plan_credits', 0) + data_row.get('purchased_credits', 0)
                         print("👉 采用了 'plan_credits + purchased_credits' 计算余额")
                    else:
                        # 如果都没有，尝试减法：总获得 - 总使用
                        total = data_row.get('total_credits', 0)
                        used = data_row.get('used_credits', 0) # 假设有 usage 字段
                        available = total - used if used else total
                        print(f"👉 采用了计算逻辑: 总计({total}) - 已用({used}) = {available}")
                    
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
💰 <b>当前余额</b>: <code>{available}</code>
📊 <b>系统状态</b>: {status_msg}
        """
        
        print("\n" + msg)
        
        notifier = LoomiNotifier()
        notifier.send_telegram("Loomi 签到提醒", msg)
        notifier.send_pushplus("Loomi 签到提醒", msg)

if __name__ == "__main__":
    LoomiClient().run()
