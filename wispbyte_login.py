# wispbyte_login.py  —— 终极保活版（强制过 Turnstile + 自动续期 cookie）
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
    # 1. 先尝试用本地 cookie 快速登录
    if os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE) as f:
            cookies = json.load(f)
        s = requests.Session()
        for name, value in cookies.items():
            s.cookies.set(name, value, domain="wispbyte.com")
        s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        r = s.get("https://wispbyte.com/client/dashboard")
        if r.status_code == 200 and "login" not in r.url:
            print("本地 cookie 有效，直接登录成功！")
            return s

    # 2. cookie 失效 → 用 Selenium 重新登录
    print("cookie 已过期，正在用 Selenium 重新登录并过 Turnstile...")
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    driver = webdriver.Chrome(options=options)
    try:
        driver.get("https://wispbyte.com/client")

        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "email")))

        driver.find_element(By.ID, "email").send_keys(os.getenv("WISPBYTE_EMAIL"))
        driver.find_element(By.ID, "password").send_keys(os.getenv("WISPBYTE_PASSWORD"))

        print("等待 Turnstile 自动验证（最长 25 秒）...")
        WebDriverWait(driver, 25).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='cf-turnstile-response'][value!='']"))
        )

        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        WebDriverWait(driver, 15).until(EC.url_contains("/dashboard"))
        print("登录成功！正在保存新 cookie...")

        cookies = {}
        for c in driver.get_cookies():
            cookies[c['name']] = c['value']

        with open(COOKIE_FILE, "w") as f:
            json.dump(cookies, f)

        # 返回 requests 能用的 session
        s = requests.Session()
        for name, value in cookies.items():
            s.cookies.set(name, value, domain="wispbyte.com")
        return s

    finally:
        driver.quit()

if __name__ == "__main__":
    session = get_valid_session()
    # 简单验证一下
    r = session.get("https://wispbyte.com/client/api/user")
    try:
        user_info = r.json()
        print("最终登录成功！当前用户：", user_info.get("username", user_info.get("email")))
    except:
        print("还是失败了，返回内容：", r.text[:500])
