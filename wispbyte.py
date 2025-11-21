# wispbyte.py —— 2025年 多账号+北京时间+完整修复版
import os
import requests
import time
from datetime import datetime, timedelta, timezone

# 获取北京时间
def get_beijing_time_str(fmt='%Y-%m-%d %H:%M:%S'):
    utc_now = datetime.now(timezone.utc)
    bj_now = utc_now + timedelta(hours=8)
    return bj_now.strftime(fmt)

def log(msg):
    cur_time = get_beijing_time_str('%H:%M:%S')
    # flush=True 确保日志在 GitHub Actions 实时显示
    print(f"[{cur_time}] {msg}", flush=True)

def send_telegram(message):
    token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    
    if not token or not chat_id:
        log("⚠️ 未检测到 Telegram 变量，跳过发送通知。")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=10)
        log("✅ Telegram 通知已发送")
    except Exception as e:
        log(f"⚠️ Telegram 发送失败: {e}")

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
        # 访问主页检测跳转
        r = s.get("https://wispbyte.com/client", timeout=20, allow_redirects=True)
        
        # 成功判断：停留在 dashboard 或者 状态码 200 且没跳回 login
        if "login" not in r.url and ("dashboard" in r.url or r.status_code == 200):
            log(f"✅ 账号 {index} 保活成功")
            return f"✅ 账号 {index}: 保活成功 (Dashboard)"
        elif "login" in r.url:
            log(f"❌ 账号 {index} Cookie 失效")
            return f"❌ 账号 {index}: Cookie 失效 (需更新)"
        else:
            return f"⚠️ 账号 {index}: 未知状态 ({r.status_code})"
            
    except Exception as e:
        log(f"❌ 账号 {index} 发生异常: {e}")
        return f"❌ 账号 {index}: 运行出错"

def run_all():
    # 1. 获取并分割 Cookie
    # 这里使用 '&' 作为分隔符
    raw_cookies = os.getenv("WISPBYTE_COOKIE_STRING", "")
    if not raw_cookies:
        log("❌ 错误：未设置 WISPBYTE_COOKIE_STRING")
        exit(1)
        
    cookie_list = [c for c in raw_cookies.split('&') if c.strip()]
    log(f"共检测到 {len(cookie_list)} 个账号")

    results = []
    
    # 2. 循环执行 (你之前的代码就是缺了这一大段！)
    for i, cookie in enumerate(cookie_list):
        res = check_one_account(i + 1, cookie)
        results.append(res)
        # 稍微暂停一下，防止并发太快
        if i < len(cookie_list) - 1:
            time.sleep(3)

    # 3. 汇总发送通知
    bj_time = get_beijing_time_str()
    summary = "\n".join(results)
    
    tg_msg = (
        f"🖥 **Wispbyte 保活报告**\n"
        f"📅 时间: `{bj_time}`\n"
        f"------------------\n"
        f"{summary}"
    )
    
    send_telegram(tg_msg)

if __name__ == "__main__":
    run_all()
