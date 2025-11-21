# wispbyte_login.py —— 2025年11月21日最终核弹版（强制过交互式 Turnstile）
import os
import json
import requests
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains

COOKIE_FILE = "wispbyte_cookies.json"

def get_valid_session():
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
                print("本地 cookie 有效，保活成功！")
                return s
        except:
            pass

    print("Cookie 已过期，正在启动终极反检测浏览器...")
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1366,768")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => false});")
    
    wait = WebDriverWait(driver, 60)  # 延长到 60 秒

    try:
        driver.get("https://wispbyte.com/client")
        wait.until(lambda d: d.find_element(By.ID, "email").is_displayed())

        driver.find_element(By.ID, "email").send_keys(os.getenv("WISPBYTE_EMAIL"))
        driver.find_element(By.ID, "password").send_keys(os.getenv("WISPBYTE_PASSWORD"))

        print("正在等待 Turnstile（可能需要点击或滑块，最多 60 秒）...")

        # 关键：如果出现交互式挑战，尝试点击 Turnstile 框触发自动通过
        try:
            iframe = driver.find_element(By.CSS_SELECTOR, "iframe[title*='challenge']")
            driver.switch_to.frame(iframe)
            checkbox = driver.find_element(By.ID, "checkbox")
            if checkbox:
                ActionChains(driver).move_to_element(checkbox).click().perform()
                print("检测到交互挑战，已自动点击复选框...")
            driver.switch_to.default_content()
        except:
            pass

        # 等 token 出现（长度 > 100 才算成功）
        def token_ready(d):
            try:
                token = d.find_element(By.NAME, "cf-turnstile-response").get_attribute("value")
                return len(token) > 100
            except:
                return False

        wait.until(token_ready)
        print("Turnstile 验证成功！")

        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        wait.until(lambda d: "/dashboard" in d.current_url)
        print("登录成功！正在保存 cookie...")

        cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
        with open(COOKIE_FILE, "w") as f:
            json.dump(cookies, f)

        session = requests.Session()
        for k, v in cookies.items():
            session.cookies.set(k, v, domain="wispbyte.com")
        
        # 保活增强：访问几个页面模拟真人
        session.get("https://wispbyte.com/client/dashboard")
        session.get("https://wispbyte.com/client/servers")
        print("保活完成，你的服务器已彻底激活！")
        return session

    except Exception as e:
        print("最终还是失败了:", str(e))
        driver.save_screenshot("final_error.png")
        raise
    finally:
        driver.quit()

if __name__ == "__main__":
    for attempt in range(3):  # 失败自动重试 3 次
        try:
            session = get_valid_session()
            user = session.get("https://wispbyte.com/client/api/user").json()
            print(f"最终保活成功！用户：{user.get('username') or user.get('email')} | 服务器上限：{user.get('serverLimit')}")
            break
        except:
            print(f"第 {attempt+1} 次尝试失败，60 秒后重试...")
            time.sleep(60)
    else:
        print("3 次尝试全部失败，账号可能被临时风控，请手动登录一次解锁")
        exit(1)
