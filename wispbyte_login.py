import requests
from bs4 import BeautifulSoup
import json
import time
import os

# ================== 请在这里填你的账号密码 ==================
EMAIL_OR_USERNAME = "dxs1256@163.com"   # 改成你的
PASSWORD = "6TwZ@QQ$b2"                   # 改成你的
# ===========================================================

# 登录页面和 API
LOGIN_PAGE = "https://wispbyte.com/client"
LOGIN_API = "https://wispbyte.com/client/api/auth/login"
DASHBOARD = "https://wispbyte.com/client/dashboard"

# 保存 cookies 的文件（下次运行可以免登录）
COOKIES_FILE = "wispbyte_cookies.json"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Origin": "https://wispbyte.com",
    "Referer": "https://wispbyte.com/client",
    "Sec-Fetch-Mode": "cors",
})

def load_cookies():
    if os.path.exists(COOKIES_FILE):
        try:
            session.cookies.update(requests.utils.cookiejar_from_dict(json.load(open(COOKIES_FILE))))
            print("已加载本地 cookies，尝试免登录...")
            if check_login():
                return True
        except:
            pass
    return False

def save_cookies():
    cookies_dict = requests.utils.dict_from_cookiejar(session.cookies)
    json.dump(cookies_dict, open(COOKIES_FILE, "w"))
    print(f"cookies 已保存到 {COOKIES_FILE}，下次运行可免登录")

def check_login():
    r = session.get(DASHBOARD, allow_redirects=False)
    if r.status_code == 200 and "dashboard" in r.text.lower():
        print("免登录成功！已进入控制面板")
        return True
    return False

def get_turnstile_token():
    # Wispbyte 用的是 Cloudflare Turnstile 无感验证，只要正常请求页面就会自动生成 token
    print("正在获取 Turnstile token...")
    r = session.get(LOGIN_PAGE)
    soup = BeautifulSoup(r.text, "html.parser")
    
    # 找到 sitekey（虽然现在是自动模式，但保留备用）
    turnstile_div = soup.find("div", {"class": "cf-turnstile"}) or soup.find("script", src="https://challenges.cloudflare.com/turnstile")
    if not turnstile_div:
        print("未检测到 Turnstile，可能是无感模式")
    
    # 等几秒让 Turnstile 自动完成验证（无头浏览器不需要手动点）
    time.sleep(4)
    
    # 直接从页面里提取 cf-turnstile-response（如果已经生成了）
    token_input = soup.find("input", {"name": "cf-turnstile-response"})
    if token_input and token_input.get("value"):
        return token_input["value"]
    
    # 大多数情况下不需要手动传 token，Cloudflare 会通过 cookie 自动验证
    return None

def login():
    print("正在登录 Wispbyte...")
    
    # 先访问一次登录页，建立必要 cookies 和 Turnstile
    get_turnstile_token()
    
    payload = {
        "identifier": EMAIL_OR_USERNAME,   # 邮箱或用户名
        "password": PASSWORD
        # Turnstile token 不需要手动传，Cloudflare 会自动验证
    }
    
    r = session.post(LOGIN_API, json=payload)
    
    try:
        result = r.json()
    except:
        result = {}
    
    if r.status_code == 200 and (result.get("success") or "dashboard" in r.url or check_login()):
        print("登录成功！")
        save_cookies()
        return True
    else:
        print("登录失败")
        print("返回内容:", r.text[:500])
        return False

def main():
    if not load_cookies():
        if login():
            print("欢迎回来！你现在已登录 Wispbyte 控制面板")
            # 这里可以继续做你想做的事，比如列出服务器、启动、重启等
            # 例如：session.get("https://wispbyte.com/client/api/servers").json()
        else:
            print("登录失败，请检查账号密码是否正确")
    else:
        print("已登录，可直接操作你的服务器")

if __name__ == "__main__":
    main()
