# wispbyte_login.py —— 2025年11月21日终极核弹版（强制 SOCKS5 + 兼容所有 Selenium 版本）
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
    # ============ 步骤1：尝试本地 cookie 快速登录 ============
    log("正在检查本地 cookie...")
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
                log("本地 cookie 有效，秒进面板成功！保活完成～")
                return s
            else:
                log("本地 cookie 已过期，需要重新登录")
        except Exception as e:
            log(f"读取 cookie 失败: {e}")

    # ============ 步骤2：强制走 SOCKS5 代理绕过 Cloudflare 风控 ============
    proxy_url = os.getenv("SOCKS5_PROXY")
    if not proxy_url:
        log("未设置 SOCKS5_PROXY 环境变量！无法绕过 Cloudflare 封锁！")
        exit(1)

    log(f"使用 SOCKS5 代理 {proxy_url} 强制绕过封锁...")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1366,768")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # 兼容所有 Selenium 版本的 SOCKS5 代理写法（关键！）
    proxy = Proxy()
    proxy.proxy_type = ProxyType.MANUAL
    proxy.socks_proxy = proxy_url
    proxy.socks_version = 5

    capabilities = webdriver.DesiredCapabilities.CHROME.copy()
    capabilities.update(proxy.to_capabilities())  # 正确写法，无参数

    driver = webdriver.Chrome(options=options, desired_capabilities=capabilities)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => false});")

    wait = WebDriverWait(driver, 80)

    try:
        log("正在通过代理打开登录页面...")
        driver.get("https://wispbyte.com/client")

        log("填写账号密码...")
        wait.unure.until(lambda d: d.find_element(By.ID, "email").is_displayed())
        driver.find_element(By.ID, "email").send_keys(os.getenv("WISPBYTE_EMAIL"))
        driver.find_element(By.ID, "password").send_keys(os.getenv("WISPBYTE_PASSWORD"))

        log("等待 Turnstile 验证（代理后通常 5-20 秒自动通过）...")

        def token_ready(d):
            try:
                t = d.find_element(By.NAME, "cf-turnstile-response").get_attribute("value")
                return len(t) > 100
            except:
                return False

        wait.until(token_ready)
        log("Turnstile 验证成功！")

        log("点击登录...")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        wait.until(lambda d: "/dashboard" in d.current_url)
        log("登录成功！正在保存最新 cookie...")

        cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
        with open(COOKIE_FILE, "w") as f:
            json.dump(cookies, f)
        log("新 cookie 已保存，下次将直接秒进")

        # 返回 requests session（也走代理）
        session = requests.Session()
        session.proxies = {"http": f"socks5://{proxy_url}", "https": f"socks5://{proxy_url}"}
        for k, v in cookies.items():
            session.cookies.set(k, v, domain="wispbyte.com")

        # 模拟真人操作
        session.get("https://wispbyte.com/client/dashboard")
        session.get("https://wispbyte.com/client/servers")
        log("保活完成！你的免费服务器已彻底激活")

        return session

    except Exception as e:
        log(f"登录失败: {e}")
        driver.save_screenshot("LOGIN_FAILED.png")
        log("已保存错误截图 LOGIN_FAILED.png")
        raise
    finally:
        driver.quit()

# ============ 主程序 ============
if __name__ == "__main__":
    for attempt in range(1, 4):
        try:
            session = get_valid_session()
            user = session.get("https://wispbyte.com/client/api/user").json()
            username = user.get("username") or user.get("email", "未知用户")
            limit = user.get("serverLimit", "未知")
            log(f"最终保活成功！用户：{username} | 服务器上限：{limit}")
            break
        except:
            log(f"第 {attempt}/3 次尝试失败，60 秒后重试...")
            time.sleep(60)
    else:
        log("所有尝试均失败！请检查代理是否可用、密码是否正确，或手动登录一次解风控")
        exit(1)
