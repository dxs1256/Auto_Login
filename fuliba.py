#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import re
import time
import random
import os
from urllib3.util import Retry
from requests.adapters import HTTPAdapter

# ==================== 从环境变量读取账号（推荐） ====================
# 支持多账号格式： user1:pass1|||user2:pass2|||user3:pass3
WNFLB_USERS = os.getenv("WNFLB_USERS", "")

if WNFLB_USERS:
    pairs = [x.strip() for x in WNFLB_USERS.split("|||") if x.strip()]
    ACCOUNTS = [{"user": p.split(":")[0], "pass": p.split(":")[1]} for p in pairs]
else:
    # 兼容旧版单账号
    ACCOUNTS = [{
        "user": os.getenv("WNFLB_USERNAME", ""),
        "pass": os.getenv("WNFLB_PASSWORD", "")
    }]

# ==================== 域名列表（自动轮询活的） ====================
DOMAINS = [
    "https://www.wnflb2023.com",
    "https://www.wnflb2024.com",
    "https://www.wnflb2025.com",
    "https://www.wnflb2026.com",
    "https://www.wnflb2027.com",
    "https://wnflb.org",
    "https://wnflb.co",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36",
    "Referer": "https://www.wnflb2023.com/forum.php",
}

def get_work_domain(session):
    for domain in DOMAINS:
        try:
            resp = session.get(domain + "/forum.php", timeout=10)
            if resp.status_code == 200 and "福利吧" in resp.text:
                print(f"[+] 找到可用域名: {domain}")
                return domain.rstrip("/")
        except:
            continue
    raise Exception("所有域名都挂了...")

def login(session, base_url, username, password):
    resp = session.get(f"{base_url}/forum.php")
    formhash = re.search(r'name="formhash" value="([^"]+)"', resp.text)
    if not formhash:
        raise Exception("获取 formhash 失败")
    formhash = formhash.group(1)

    login_url = f"{base_url}/member.php?mod=logging&action=login&loginsubmit=yes&inajax=1"
    data = {
        "formhash": formhash,
        "referer": f"{base_url}/forum.php",
        "loginfield": "username",
        "username": username,
        "password": password,
        "questionid": "0",
        "answer": "",
        "cookietime": "2592000",
    }
    resp = session.post(login_url, data=data, headers={"X-Requested-With": "XMLHttpRequest"})
    if "succeedhandle_logging" in resp.text or "欢迎您回来" in resp.text:
        print(f"[+] {username} 登录成功")
        return True
    else:
        print(f"[-] {username} 登录失败")
        print(resp.text[:300])
        return False

def sign_in(session, base_url):
    sign_url = f"{base_url}/plugin.php?id=fx_checkin:checkin"
    resp = session.get(sign_url, timeout=10)
    if "已签到" in resp.text or "今日已经签到" in resp.text:
        print("[+] 今天已经签到过了")
        return True
    elif "签到成功" in resp.text:
        reward = re.search(r"获得([^ ]+)威望", resp.text)
        print(f"[+] 签到成功！{reward.group(0) if reward else ''}")
        return True
    else:
        print("[-] 签到失败")
        print(resp.text[:500])
        return False

def main():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1)
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(HEADERS)

    for account in ACCOUNTS:
        if not account["user"] or not account["pass"]:
            continue
        print(f"\n正在为 {account['user']} 签到...")
        try:
            base_url = get_work_domain(session)
            if login(session, base_url, account["user"], account["pass"]):
                sign_in(session, base_url)
            time.sleep(random.uniform(3, 8))
        except Exception as e:
            print(f"[-] 出错了: {e}")
        session.cookies.clear()

if __name__ == "__main__":
    main()
