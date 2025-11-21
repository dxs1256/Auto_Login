# wispbyte.py —— 2025年 北京时间版
import os
import requests
import time
from datetime import datetime, timedelta, timezone

#以此确保获取到的是北京时间 (UTC+8)
def get_beijing_time_str(fmt='%Y-%m-%d %H:%M:%S'):
    utc_now = datetime.now(timezone.utc)
    bj_now = utc_now + timedelta(hours=8)
    return bj_now.strftime(fmt)

def log(msg):
    # 日志也显示北京时间，方便查看
    cur_time = get_beijing_time_str('%H:%M:%S')
    print(f"[{cur_time}] {msg}")

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
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
        log("✅ Telegram 通知已发送")
    except Exception as e:
        log(f"⚠️ Telegram 发送失败: {e}")

def keep_alive():
    cookie_str = os.getenv("WISPBYTE_COOKIE_STRING")
    if not cookie_str:
        log("❌ 错误：未设置 WISPBYTE_COOKIE_STRING")
        send_telegram("🚨 **Wispbyte 保活失败**\n\n原因：未设置 Cookie 环境变量！")
        exit(1)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Cookie": cookie_str,
        "Referer": "https://wispbyte.com/client"
    }

    proxies = None
    proxy_url = os.getenv("SOCKS5_PROXY")
    if proxy_url:
        proxies = {"http": f"socks5://{proxy_url}", "https": f"socks5://{proxy_url}"}
        log(f"使用代理: {proxy_url}")
    
    s = requests.Session()
    s.headers.update(headers)
    s.proxies = proxies

    target_url = "https://wispbyte.com/client"
    
    try:
        log(f"正在尝试访问页面: {target_url}")
        r = s.get(target_url, timeout=20, allow_redirects=True)
        log(f"最终 URL: {r.url}")

        # --- 成功判断逻辑 ---
        if "login" not in r.url and ("dashboard" in r.url or r.status_code == 200):
            # 获取北京时间用于通知
            bj_time_str = get_beijing_time_str()
            
            msg = (
                "✅ **Wispbyte 保活成功**\n\n"
                f"📅 时间: `{bj_time_str} (北京时间)`\n"
                f"🔗 状态: 已进入 Dashboard\n"
                f"🍪 Cookie: 有效续期中"
            )
            log("保活成功！准备发送通知...")
            send_telegram(msg)
            return True
        
        # --- 失败判断逻辑 ---
        elif "login" in r.url:
            err_msg = "🚨 **Wispbyte 保活失败**\n\nCookie 已失效，重定向回了登录页！请尽快更新 Secrets。"
            log(err_msg)
            send_telegram(err_msg)
            raise Exception("Cookie Expired")
        
        else:
            raise Exception(f"Unknown Status {r.status_code}")

    except Exception as e:
        log(f"❌ 异常: {e}")
        send_telegram(f"🚨 **Wispbyte 运行异常**\n\n错误信息: `{str(e)}`")
        raise e

if __name__ == "__main__":
    for i in range(3):
        try:
            if keep_alive():
                break
        except:
            time.sleep(10)
    else:
        exit(1)
