# wispbyte_login.py —— 最终带日志版（GitHub Actions 完美运行）
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

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def get_valid_session():
    # ==================== 步骤1：尝试本地 cookie ====================
    log("正在检查本地 cookie 是否可用...")
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
                log("本地 cookie 有效！秒进面板，保活成功～")
                return s
            else:
                log("本地 cookie 已过期，需要重新登录")
        except Exception as e:
            log(f"读取 cookie 失败: {e}")

    # ==================== 步骤2：启动浏览器重新登录 ====================
    log("正在启动无头 Chrome（最强反检测模式）...")
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1366,768")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => false});")
    wait = WebDriverWait(driver, 60)

    try:
        log("正在打开 Wispbyte 登录页面...")
        driver.get("https://wispbyte.com/client")

        log("正在填写账号密码...")
        wait.until(lambda d: d.find_element(By.ID, "email").is_displayed())
        driver.find_element(By.ID, "email").clear()
        driver.find_element(By.ID, "email").send_keys(os.getenv("WISPBYTE_EMAIL"))
        driver.find_element(By.ID, "password").clear()
        driver.find_element(By.ID, "password").send_keys(os.getenv("WISPBYTE_PASSWORD"))

        log("等待 Cloudflare Turnstile 验证（最多 60 秒，可能需要自动点击）...")

        # 如果出现交互式挑战，自动点击
        try:
            iframe = wait.until(lambda d: d.find_element(By.CSS_SELECTOR, "iframe[title*='widget']"))
            driver.switch_to.frame(iframe)
            checkbox = driver.find_element(By.CSS_SELECTOR, ".ctp-checkbox-label")
            ActionChains(driver).move_to_element(checkbox).click().perform()
            log("检测到交互式 Turnstile，已自动点击复选框")
            driver.switch_to.default_content()
        except:
            log("当前为无感模式或已自动完成")

        # 等待 token 生成
        def token_ok(d):
            try:
                t = d.find_element(By.NAME, "cf-turnstile-response").get_attribute("value")
                return len(t) > 100
            except:
                return False

        wait.until(token_ok)
        log("Turnstile 验证成功！")

        log("正在点击登录按钮...")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        wait.until(lambda d: "/dashboard" in d.current_url)
        log("登录成功！正在保存新 cookie...")

        cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
        with open(COOKIE_FILE, "w") as f:
            json.dump(cookies, f)
        log("新 cookie 已保存，下次将秒进")

        # 返回 requests session
        session = requests.Session()
        for k, v in cookies.items():
            session.cookies.set(k, v, domain="wispbyte.com")

        # 模拟真人操作，防止被检测不活跃
        log("正在访问 Dashboard 和服务器列表，彻底激活账号...")
        session.get("https://wispbyte.com/client/dashboard")
        session.get("https://wispbyte.com/client/servers")

        return session

    except Exception as e:
        log(f"登录失败！错误信息: {e}")
        driver.save_screenshot("LOGIN_ERROR.png")
        log("已保存错误截图 LOGIN_ERROR.png")
        raise
    finally:
        driver.quit()

if __name__ == "__main__":
    for i in range(1, 4):
        try:
            session = get_valid_session()
            user = session.get("https://wispbyte.com/client/api/user").json()
            username = user.get("username") or user.get("email", "未知用户")
            limit = user.get("serverLimit", "未知")
            log(f"最终保活成功！当前用户：{username} | 服务器上限：{limit}")
            break
        except:
            log(f"第 {i}/3 次尝试失败，60 秒后重试...")
            time.sleep(60)
    else:
        log("所有尝试都失败了！请手动登录一次解风控，或检查密码是否正确")
        exit(1)
