# wispbyte_login.py —— 强制 SOCKS5 代理 + 最强反检测（2025核弹版）
import os
import json
import requests
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.proxy import Proxy, ProxyType

COOKIE_FILE = "wispbyte_cookies.json"

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def get_valid_session():
    # 尝试本地 cookie
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE) as f:
                cookies = json.load(f)
            s = requests.Session()
            for k, v in cookies.items():
                s.cookies.set(k, v, domain="wispbyte.com")
            s.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            r = s.get("https://wispbyte.com/client/api/user")
            if r.status_code == 200 and r.json().get("username"):
                log("本地 cookie 有效，保活成功！")
                return s
        except:
            log("本地 cookie 失效")

    proxy_url = os.getenv("SOCKS5_PROXY")  # 例如: 127.0.0.1:1080
    if not proxy_url:
        log("未检测到 SOCKS5_PROXY 环境变量！无法绕过 Cloudflare 风控")
        exit(1)

    log(f"检测到 SOCKS5 代理 {proxy_url}，正在强制走代理绕过封锁...")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1366,768")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # 强制 Selenium 走 SOCKS5 代理（兼容 Selenium 4.11+）
    proxy = Proxy()
    proxy.proxy_type = ProxyType.MANUAL
    proxy.socks_proxy = proxy_url
    proxy.socks_version = 5

    capabilities = webdriver.DesiredCapabilities.CHROME.copy()
    proxy.to_capabilities(capabilities)

    driver = webdriver.Chrome(options=options, desired_capabilities=capabilities)

    wait = WebDriverWait(driver, 80)

    try:
        log("正在通过代理打开 Wispbyte 登录页...")
        driver.get("https://wispbyte.com/client")

        log("填写账号密码...")
        wait.until(lambda d: d.find_element(By.ID, "email").is_displayed())
        driver.find_element(By.ID, "email").send_keys(os.getenv("WISPBYTE_EMAIL"))
        driver.find_element(By.ID, "password").send_keys(os.getenv("WISPBYTE_PASSWORD"))

        log("等待 Turnstile 验证（走代理后通常 5-15 秒自动通过）...")

        def token_ready(d):
            try:
                t = d.find_element(By.NAME, "cf-turnstile-response").get_attribute("value")
                return len(t) > 100
            except:
                return False

        wait.until(token_ready)
        log("Turnstile 验证成功！（代理生效）")

        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        wait.until(lambda d: "/dashboard" in d.current_url)
        log("登录成功！保存 cookie...")

        cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
        with open(COOKIE_FILE, "w") as f:
            json.dump(cookies, f)

        session = requests.Session()
        # requests 也走代理（可选）
        session.proxies = {"http": f"socks5://{proxy_url}", "https": f"socks5://{proxy_url}"}
        for k, v in cookies.items():
            session.cookies.set(k, v, domain="wispbyte.com")

        log("保活完成！你的服务器已彻底复活")
        return session

    except Exception as e:
        log(f"登录失败: {e}")
        driver.save_screenshot("PROXY_ERROR.png")
        raise
    finally:
        driver.quit()

if __name__ == "__main__":
    session = get_valid_session()
    user = session.get("https://wispbyte.com/client/api/user").json()
    log(f"最终成功！用户：{user.get('username','') or user.get('email')} | 服务器上限：{user.get('serverLimit')}")
