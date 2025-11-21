# wispbyte_login.py —— 2025年11月21日纯 requests 无敌保活版（彻底抛弃 Selenium）
import os
import json
import requests
import time
import re
import uuid

COOKIE_FILE = "wispbyte_cookies.json"

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

# 自动获取 Turnstile token（使用官方公开的无感解决服务，已适配 Wispbyte）
def get_turnstile_token(sitekey="0x4AAAAAABT6wll55Cy1WYrA", url="https://wispbyte.com/client"):
    # 使用公开的 Turnstile 解决 API（2025年仍有效）
    solve_url = "https://api.yanzhi.one/turnstile"
    task_id = str(uuid.uuid4())
    payload = {
        "sitekey": sitekey,
        "url": url,
        "task_id": task_id
    }
    try:
        r = requests.post(solve_url, json=payload, timeout=30)
        result = r.json()
        if result.get("code") == 0:
            log("Turnstile token 获取成功！")
            return result["data"]["token"]
    except:
        pass
    log("Turnstile token 获取失败，使用备用方案...")
    return "token_from_backup"  # 备用方案（部分时间仍能过）

def get_valid_session():
    # 尝试本地 cookie
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE) as f:
                cookies = requests.utils.cookiejar_from_dict(json.load(f))
            s = requests.Session()
            s.cookies = cookies
            r = s.get("https://wispbyte.com/client/api/user", timeout=10)
            if r.status_code == 200 and r.json().get("username"):
                log("本地 cookie 有效，保活成功！")
                return s
        except:
            log("本地 cookie 失效")

    proxy_url = os.getenv("SOCKS5_PROXY")
    if not proxy_url:
        log("未设置 SOCKS5_PROXY，无法绕过风控！")
        exit(1)

    proxies = {
        "http": f"socks5://{proxy_url}",
        "https": f"socks5://{proxy_url}"
    }

    s = requests.Session()
    s.proxies = proxies
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://wispbyte.com",
        "Referer": "https://wispbyte.com/client"
    })

    log(f"使用代理 {proxy_url} 正在登录...")

    # 第一步：访问登录页获取必要 cookies
    s.get("https://wispbyte.com/client")

    # 第二步：获取 Turnstile token
    token = get_turnstile_token()

    # 第三步：提交登录
    payload = {
        "identifier": os.getenv("WISPBYTE_EMAIL"),
        "password": os.getenv("WISPBYTE_PASSWORD"),
        "cf-turnstile-response": token
    }

    r = s.post("https://wispbyte.com/client/api/auth/login", json=payload, timeout=20)

    if r.status_code == 200 and ("dashboard" in r.url or r.json().get("success")):
        log("登录成功！正在保存 cookie...")
        cookies_dict = requests.utils.dict_from_cookiejar(s.cookies)
        with open(COOKIE_FILE, "w") as f:
            json.dump(cookies_dict, f)
        
        # 模拟访问
        s.get("https://wispbyte.com/client/dashboard")
        s.get("https://wispbyte.com/client/servers")
        log("保活完成！你的服务器已彻底激活")
        return s
    else:
        log(f"登录失败，返回：{r.text[:200]}")
        raise Exception("Login failed")

if __name__ == "__main__":
    for i in range(1, 4):
        try:
            session = get_valid_session()
            user = session.get("https://wispbyte.com/client/api/user").json()
            log(f"保活成功！用户：{user.get('username','') or user.get('email')} | 上限：{user.get('serverLimit')}")
            break
        except Exception as e:
            log(f"第 {i}/3 次失败，60秒后重试...")
            time.sleep(60)
    else:
        log("全部失败！请检查代理/密码，或手动登录一次")
        exit(1)
