# wispbyte.py —— 2025年 账号设置页面精准提取版
import os
import requests
import time
import re
from datetime import datetime, timedelta, timezone

# 获取北京时间
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
    
    if not token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=10)
        log("✅ Telegram 通知已发送")
    except Exception as e:
        log(f"⚠️ Telegram 发送失败: {e}")

def send_pushplus(message):
    """发送 PushPlus 通知"""
    token = os.getenv("PUSHPLUS_TOKEN")
    
    if not token:
        return

    url = "http://www.pushplus.plus/send"
    content = message.replace("\n", "<br>")

    payload = {
        "token": token,
        "title": "Wispbyte 保活通知",
        "content": content,
        "template": "html",
        "channel": "wechat"
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            resp_json = r.json()
            if resp_json.get("code") == 200:
                log("✅ PushPlus 通知已发送")
            else:
                log(f"⚠️ PushPlus 返回错误: {resp_json.get('msg')}")
    except Exception as e:
        log(f"⚠️ PushPlus 发送失败: {e}")

# 单个账号保活逻辑
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
        
        # 访问账号设置页面
        r = s.get("https://wispbyte.com/client/account-settings", timeout=20, allow_redirects=True)
        
        # 判断是否被重定向到了登录页（说明Cookie失效）
        if "login" in r.url:
            log(f"❌ 账号 {index} Cookie 失效，重定向至登录页")
            return f"❌ 账号 {index}：Cookie 已失效"

        if r.status_code == 200:
            # --- 调试与提取逻辑 ---
            # 1. 抓取页面中所有的 input 输入框的值（通常邮箱会显示在某个 input 里）
            inputs = re.findall(r'<input[^>]+value=["\']([^"\']+)["\'][^>]*>', r.text)
            log(f"调试：页面输入框发现的值: {inputs}")

            # 2. 直接使用正则匹配页面中出现的所有邮箱地址
            emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', r.text)
            
            # 过滤掉可能存在的官方客服邮箱（防止抓错）
            user_emails = [e for e in emails if "wispbyte.com" not in e.lower()]

            if user_emails:
                username = user_emails[0]  # 获取匹配到的第一个真实邮箱
            else:
                username = "未知用户"
                log("调试：正则未能匹配到邮箱格式")

            log(f"✅ 账号 {index} ({username}) 保活成功")
            return f"✅ 账号 {index}：<b>{username}</b> (正常)"
            
        else:
            return f"⚠️ 账号 {index}：页面访问异常 ({r.status_code})"
            
    except Exception as e:
        log(f"❌ 账号 {index} 发生异常: {e}")
        return f"❌ 账号 {index}：运行出错"

def run_all():
    raw_cookies = os.getenv("WISPBYTE_COOKIE_STRING", "")
    if not raw_cookies:
        log("❌ 错误：未设置 WISPBYTE_COOKIE_STRING")
        exit(1)
        
    cookie_list = [c for c in raw_cookies.split('&') if c.strip()]
    log(f"共检测到 {len(cookie_list)} 个账号")

    results = []
    
    for i, cookie in enumerate(cookie_list):
        res = check_one_account(i + 1, cookie)
        results.append(res)
        if i < len(cookie_list) - 1:
            time.sleep(3)

    bj_time = get_beijing_time_str()
    summary = "\n".join(results)
    
    tg_msg = (
        f"🖥 <b>Wispbyte 保活报告</b>\n"
        f"📅 时间：{bj_time}\n"
        f"------------------\n"
        f"{summary}"
    )
    
    # 发送 Telegram 通知
    send_telegram(tg_msg)
    
    # 发送 PushPlus 通知
    send_pushplus(tg_msg)

if __name__ == "__main__":
    run_all()
