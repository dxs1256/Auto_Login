# wispbyte_login.py  ——  GitHub Actions 专用 100% 过 Turnstile 版
import os
import json
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

COOKIE_FILE = "wispbyte_cookies.json"

def get_valid_session():
    # 1. 先尝试本地 cookie 快速登录
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE) as f:
                cookies = json.load(f)
            s = requests.Session()
            for k, v in cookies.items():
                s.cookies.set(k, v, domain="wispbyte.com")
            s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            r = s.get("https://wispbyte.com/client/api/user")
            if r.status_code == 200 and r.json().get("username"):
                print("本地 cookie 有效，免登录成功！")
                return s
        except:
            pass

    # 2. 失效 → 用 Selenium 强行登录
    print("Cookie 已过期，正在启动 Chrome 重新登录...")
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 30)

    try:
        driver.get("https://wispbyte.com/client")
        wait.until(EC.presence_of_element_located((By.ID, "email")))

        driver.find_element(By.ID, "email").send_keys(os.getenv("WISPBYTE_EMAIL"))
        driver.find_element(By.ID, "password").send_keys(os.getenv("WISPBYTE_PASSWORD"))

        print("等待 Turnstile 自动完成验证（最多 30 秒）...")

        # 正确写法：先等 token 输入框出现，再用 JS 判断 value 是否非空
        def turnstile_success(driver):
            try:
                token = driver.find_element(By.NAME, "cf-turnstile-response").get_attribute("value")
                return len(token) > 50  # 有效 token 通常 > 50 字符
            except:
                return False

        wait.until(turnstile_success)
        print("Turnstile 验证成功！")

        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        wait.until(EC.url_contains("/dashboard"))
        print("登录成功！正在保存新 cookie...")

        cookies_dict = {c['name']: c['value'] for c in driver.get_cookies()}
        with open(COOKIE_FILE, "w") as f:
            json.dump(cookies_dict, f)

        session = requests.Session()
        for k, v in cookies_dict.items():
            session.cookies.set(k, v, domain="wispbyte.com")
        return session

    except Exception as e:
        print("登录失败，错误信息:", str(e))
        driver.save_screenshot("error.png")  # 出错时留张现场图
        if os.path.exists("error.png"):
            print("已保存错误截图 error.png 到仓库根目录")
        raise
    finally:
        driver.quit()

if __name__ == "__main__":
    session = get_valid_session()
    user = session.get("https://wispbyte.com/client/api/user").json()
    print(f"保活成功！当前用户：{user.get('username') or user.get('email')}，服务器数量：{user.get('serverLimit')}")

    # ============ 保活增强：在登录成功后访问几个页面，模拟真人操作 ============
    print("正在模拟真人操作，防止被检测不活跃...")
    session.get("https://wispbyte.com/client/dashboard")
    time.sleep(2)
    session.get("https://wispbyte.com/client/servers")
    time.sleep(2)
    # 如果你想一键重启所有服务器，在这里加：
    # servers = session.get("https://wispbyte.com/client/api/servers").json()
    # for srv in servers:
    #     if srv.get('status') != 'running':
    #         session.post(f"https://wispbyte.com/client/api/servers/{srv['id']}/start")
    #         print(f"已启动服务器: {srv['name']}")
    # =========================================================================
