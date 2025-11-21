# wispbyte_login.py —— 2025年 Cookie 页面检测版（修复 404 错误）
import os
import requests
import time

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def keep_alive():
    # 1. 获取 Cookie
    cookie_str = os.getenv("WISPBYTE_COOKIE_STRING")
    if not cookie_str:
        log("❌ 错误：未设置 WISPBYTE_COOKIE_STRING")
        exit(1)

    # 2. 构造请求头
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Cookie": cookie_str,
        "Referer": "https://wispbyte.com/client"
    }

    # 3. 代理设置
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

    # 4. 执行保活访问 (访问主页而非 API)
    target_url = "https://wispbyte.com/client"
    
    try:
        log(f"正在尝试访问页面: {target_url}")
        r = s.get(target_url, timeout=20, allow_redirects=True)
        
        # 调试信息：打印最终跳转到的 URL
        log(f"请求结束，最终 URL: {r.url}")
        
        # 判断逻辑
        if r.status_code == 404:
            log("❌ 路径 404 错误，网站结构可能已变更。")
            # 尝试备用路径
            log("尝试访问根路径...")
            r = s.get("https://wispbyte.com/", timeout=20)
        
        # 检查是否被重定向到了登录页
        if "login" in r.url or "auth" in r.url:
            log("❌ 保活失败：Cookie 已失效，被重定向到了登录页。")
            log("⚠️ 请在浏览器重新登录，按 F12 获取最新的 Cookie 更新到 Secrets！")
            raise Exception("Cookie Expired")
        
        # 检查页面内容特征
        # 如果页面里包含 'Dashboard' 'Server' 'Logout' 等词，说明登录有效
        page_content = r.text.lower()
        if "dashboard" in page_content or "server" in page_content or "logout" in page_content or "sign out" in page_content:
            log("✅ 保活成功！页面包含登录特征。")
            return True
        
        # 兜底判断
        if r.status_code == 200:
            log("✅ 请求成功 (200 OK)，未跳转登录页，视为保活成功。")
            return True
            
        log(f"⚠️ 未知状态: {r.status_code}")
        raise Exception("Unknown Status")

    except Exception as e:
        log(f"❌ 异常: {e}")
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
