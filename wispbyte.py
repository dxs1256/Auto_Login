# wispbyte.py —— 2025年 优化提取版
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
        "Referer": "https://wispbyte.com/client/account"
    }
    s = requests.Session()
    s.headers.update(headers)

    try:
        log(f"正在检查第 {index} 个账号...")
        # 直接访问账号页面
        r = s.get("https://wispbyte.com/client/account", timeout=20, allow_redirects=True)
        
        if r.status_code == 200:
            # 使用更宽泛的正则匹配：查找页面中看起来像邮箱或用户名的文本
            # 匹配逻辑：找 @ 符号前后的文本，或者匹配特定 div 的内容
            username = "未知用户"
            
            # 1. 尝试匹配邮箱格式 (最精准的识别方式)
            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', r.text)
            if email_match:
                username = email_match.group(0)
            else:
                # 2. 如果没找到邮箱，尝试查找你在路径中提到的div内容
                # 备选：查找 class 或结构特征 (根据你的路径，通常包含用户信息)
                log("调试：未通过正则匹配到邮箱，请检查页面结构")
            
            log(f"✅ 账号 {index} ({username}) 保活成功")
            return f"✅ 账号 {index}：<b>{username}</b>"
            
        elif "login" in r.url:
            return f"❌ 账号 {index}：Cookie 已失效"
        else:
            return f"⚠️ 账号 {index}：无法访问页面 (Status: {r.status_code})"
            
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
