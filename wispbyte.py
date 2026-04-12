import os
import requests
import time
import re
from datetime import datetime, timedelta, timezone

def get_beijing_time_str(fmt='%Y-%m-%d %H:%M:%S'):
    utc_now = datetime.now(timezone.utc)
    bj_now = utc_now + timedelta(hours=8)
    return bj_now.strftime(fmt)

def log(msg):
    print(f"[{get_beijing_time_str('%H:%M:%S')}] {msg}", flush=True)

def check_one_account(index, cookie):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Cookie": cookie.strip(),
        "Referer": "https://wispbyte.com/client"
    }
    s = requests.Session()
    s.headers.update(headers)

    try:
        log(f"正在检查第 {index} 个账号...")
        # 直接访问 client 页面
        r = s.get("https://wispbyte.com/client", timeout=20, allow_redirects=True)
        
        # --- 调试代码：寻找用户信息所在的行 ---
        # 提取页面中所有包含 user 或 email 的 script 或 div 行
        debug_lines = [line.strip() for line in r.text.split('\n') if 'email' in line.lower() or 'user' in line.lower()]
        log(f"调试：页面中包含 user/email 的关键行片段: {debug_lines[:10]}")
        
        if r.status_code == 200:
            log(f"✅ 账号 {index} 成功连接 (状态: 200)")
            return f"✅ 账号 {index}：(连接成功)"
        else:
            return f"⚠️ 账号 {index}：访问异常 (Status: {r.status_code})"
            
    except Exception as e:
        log(f"❌ 账号 {index} 发生异常: {e}")
        return f"❌ 账号 {index}：运行出错"

def run_all():
    raw_cookies = os.getenv("WISPBYTE_COOKIE_STRING", "")
    if not raw_cookies:
        log("❌ 错误：未设置 WISPBYTE_COOKIE_STRING")
        exit(1)
        
    cookie_list = [c for c in raw_cookies.split('&') if c.strip()]
    results = [check_one_account(i + 1, cookie) for i, cookie in enumerate(cookie_list)]
    
    summary = "\n".join(results)
    msg = f"🖥 <b>Wispbyte 保活报告</b>\n📅 {get_beijing_time_str()}\n------------------\n{summary}"
    
    # 这里保持原有逻辑发送通知
    if os.getenv("TG_BOT_TOKEN"):
        requests.post(f"https://api.telegram.org/bot{os.getenv('TG_BOT_TOKEN')}/sendMessage", 
                      json={"chat_id": os.getenv("TG_CHAT_ID"), "text": msg, "parse_mode": "HTML"})
    
    if os.getenv("PUSHPLUS_TOKEN"):
        requests.post("http://www.pushplus.plus/send", 
                      json={"token": os.getenv("PUSHPLUS_TOKEN"), "title": "Wispbyte 保活通知", "content": msg.replace("\n", "<br>"), "template": "html"})

if __name__ == "__main__":
    run_all()
