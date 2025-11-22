# wispbyte.py —— 2025年 用户名提取增强版 + PushPlus
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
        log("⚠️ 未检测到 Telegram 变量，跳过 Telegram 通知。")
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
        log("⚠️ 未检测到 PUSHPLUS_TOKEN，跳过 PushPlus 通知。")
        return

    url = "http://www.pushplus.plus/send"
    
    # PushPlus 的 html 模板中，需要用 <br> 换行
    # 将原始消息中的换行符替换为 HTML 换行标签
    content = message.replace("\n", "<br>")

    payload = {
        "token": token,
        "title": "Wispbyte 保活通知",
        "content": content,
        "template": "html",  # 使用 html 模板以兼容 <b> 等标签
        "channel": "wechat"  # 默认发送到微信
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            # PushPlus 即使请求成功也可能返回错误码（如token错误），简单检查一下响应体
            resp_json = r.json()
            if resp_json.get("code") == 200:
                log("✅ PushPlus 通知已发送")
            else:
                log(f"⚠️ PushPlus 返回错误: {resp_json.get('msg')}")
        else:
            log(f"⚠️ PushPlus 请求异常: {r.status_code}")
    except Exception as e:
        log(f"⚠️ PushPlus 发送失败: {e}")

# 单个账号保活逻辑
def check_one_account(index, cookie):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Cookie": cookie.strip(),
        "Referer": "https://wispbyte.com/client"
    }
    
    proxies = None
    proxy_url = os.getenv("SOCKS5_PROXY")
    if proxy_url:
        proxies = {"http": f"socks5://{proxy_url}", "https": f"socks5://{proxy_url}"}

    s = requests.Session()
    s.headers.update(headers)
    s.proxies = proxies

    try:
        log(f"正在检查第 {index} 个账号...")
        r = s.get("https://wispbyte.com/client", timeout=20, allow_redirects=True)
        
        # 成功判断
        if "login" not in r.url and ("dashboard" in r.url or r.status_code == 200):
            # --- 提取用户名逻辑 ---
            username = "未知用户"
            try:
                match = re.search(r'<div class="username">\s*([^<]+)\s*</div>', r.text)
                if match:
                    username = match.group(1).strip()
            except Exception as e:
                log(f"提取用户名失败: {e}")

            log(f"✅ 账号 {index} ({username}) 保活成功")
            return f"✅ 账号 {index}：<b>{username}</b> (正常)"
            
        elif "login" in r.url:
            log(f"❌ 账号 {index} Cookie 失效")
            return f"❌ 账号 {index}：Cookie 已失效"
        else:
            return f"⚠️ 账号 {index}：状态未知 ({r.status_code})"
            
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
