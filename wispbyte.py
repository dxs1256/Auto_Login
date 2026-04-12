# wispbyte.py —— 2025年 Dashboard 页面提取版
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
    cur_time = get_beijing_time_str('%H:%M:%S')
    print(f"[{cur_time}] {msg}", flush=True)

def send_telegram(message):
    token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML", "disable_web_page_preview": True}
    try: requests.post(url, json=payload, timeout=10)
    except Exception as e: log(f"⚠️ Telegram 发送失败: {e}")

def send_pushplus(message):
    token = os.getenv("PUSHPLUS_TOKEN")
    if not token: return
    url = "http://www.pushplus.plus/send"
    payload = {"token": token, "title": "Wispbyte 保活通知", "content": message.replace("\n", "<br>"), "template": "html"}
    try: requests.post(url, json=payload, timeout=10)
    except Exception as e: log(f"⚠️ PushPlus 发送失败: {e}")

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
        
        # === 修改点：将请求地址改为了 dashboard ===
        r = s.get("https://wispbyte.com/client/dashboard", timeout=20, allow_redirects=True)
        
        # 验证 Cookie 是否失效
        if "login" in r.url:
            log(f"❌ 账号 {index} Cookie 已失效，重定向到了登录页")
            return f"❌ 账号 {index}：Cookie 已失效"

        if r.status_code == 200:
            username = "未知用户"
            
            # --- 精准匹配 dashboard 页面的结构 ---
            # 匹配 <div class="email">dxs1256@163.com</div> 里面的内容
            match = re.search(r'<div class="email">\s*([^<]+)\s*</div>', r.text)
            
            if match:
                username = match.group(1).strip()
            else:
                # 备用方案：如果 class 名字有变化，直接全局搜索带 @ 的邮箱格式
                emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', r.text)
                user_emails = [e for e in emails if "wispbyte.com" not in e.lower()]
                if user_emails:
                    username = user_emails[0]
                else:
                    log(f"调试：Dashboard 页面源码中未发现邮箱信息，可能是通过 JS 动态加载的。")

            log(f"✅ 账号 {index} ({username}) 保活成功")
            return f"✅ 账号 {index}：<b>{username}</b> (正常)"
        else:
            return f"⚠️ 账号 {index}：访问异常 ({r.status_code})"
            
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
    tg_msg = f"🖥 <b>Wispbyte 保活报告</b>\n📅 {get_beijing_time_str()}\n------------------\n{summary}"
    
    send_telegram(tg_msg)
    send_pushplus(tg_msg)

if __name__ == "__main__":
    run_all()
