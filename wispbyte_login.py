# wispbyte_login.py —— 2025年 Cookie 续期保活版（无需破解 Turnstile）
import os
import requests
import time

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def keep_alive():
    # 1. 获取 Cookie
    cookie_str = os.getenv("WISPBYTE_COOKIE_STRING")
    if not cookie_str:
        log("❌ 错误：未设置 WISPBYTE_COOKIE_STRING，请在 GitHub Secrets 中添加！")
        exit(1)

    # 2. 构造请求头（伪装成浏览器）
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Cookie": cookie_str,
        "Referer": "https://wispbyte.com/client/"
    }

    # 3. 代理设置（GitHub Actions 的 IP 可能会被 Cloudflare 拦截，建议配置 SOCKS5）
    proxies = None
    proxy_url = os.getenv("SOCKS5_PROXY")
    if proxy_url:
        proxies = {
            "http": f"socks5://{proxy_url}",
            "https": f"socks5://{proxy_url}"
        }
        log(f"使用代理: {proxy_url}")
    
    s = requests.Session()
    s.headers.update(headers)
    s.proxies = proxies

    # 4. 执行保活访问
    try:
        log("正在尝试访问用户信息接口...")
        # 访问 API 获取用户信息，检测 Cookie 是否有效
        r = s.get("https://wispbyte.com/client/api/user", timeout=15)
        
        if r.status_code == 200:
            data = r.json()
            username = data.get("username") or data.get("email")
            if username:
                log(f"✅ 保活成功！当前用户: {username}")
                # 顺便访问一下 Dashboard 增加活跃度
                s.get("https://wispbyte.com/client/dashboard", timeout=10)
                return True
        elif r.status_code == 401 or r.status_code == 403:
            log(f"❌ Cookie 已失效 (状态码 {r.status_code})。")
            log("⚠️ 请重新在浏览器登录，提取新的 Cookie 更新到 GitHub Secrets。")
            raise Exception("Cookie Expired")
        else:
            log(f"⚠️ 未知状态: {r.status_code} | 返回: {r.text[:100]}")
            raise Exception("Unknown Error")

    except Exception as e:
        log(f"❌ 请求异常: {e}")
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
