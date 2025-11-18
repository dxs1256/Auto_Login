#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import os
import time
import random

# 从环境变量读取多账号
WNFLB_USERS = os.getenv("WNFLB_USERS", "")
if WNFLB_USERS:
    pairs = [x.strip() for x in WNFLB_USERS.split("|||") if x.strip()]
    ACCOUNTS = [{"user": p.split(":")[0], "pass": p.split(":")[1]} for p in pairs]
else:
    ACCOUNTS = [{"user": os.getenv("WNFLB_USERNAME", ""), "pass": os.getenv("WNFLB_PASSWORD", "")}]

DOMAINS = [
    "https://www.wnflb2023.com",
    "https://www.wnflb2024.com",
    "https://www.wnflb2025.com",
    "https://wnflb.org",
    "https://wnflb.co",
]

def get_work_domain():
    session = requests.Session()
    for domain in DOMAINS:
        try:
            r = session.get(domain + "/forum.php", timeout=10)
            if r.status_code == 200 and "福利吧" in r.text:
                print(f"[+] 可用域名: {domain}")
                return domain.rstrip("/"), session
        except:
            continue
    raise Exception("所有域名都寄了...")

def direct_sign(user, password, base_url, session):
    # 直接调用 fx_checkin 的签到接口（无需登录！）
    sign_api = f"{base_url}/plugin.php?id=fx_checkin:checkin&formhash=&checkin=签到"
    
    # 伪造一点登录态（带上用户名密码的 cookie）
    session.cookies.set("discuz_user", f"{user}^{password}")
    session.cookies.set("discuz_auth", "fake")  # 随便填
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": f"{base_url}/forum.php",
    }
    
    r = session.get(sign_api, headers=headers, timeout=10)
    text = r.text
    
    if "签到成功" in text or "获得" in text:
        reward = "".join(filter(str.isdigit, text.split("获得")[1].split("威望")[0])) if "获得" in text else ""
        print(f"[+] {user} 签到成功！+{reward}威望")
        return True
    elif "已签到" in text:
        print(f"[+] {user} 今天已经签过了")
        return True
    else:
        print(f"[-] {user} 签到失败")
        print(text[:300])
        return False

def main():
    base_url, session = get_work_domain()
    for acc in ACCOUNTS:
        if not acc["user"] or not acc["pass"]:
            continue
        print(f"\n正在为 {acc['user']} 签到...")
        direct_sign(acc["user"], acc["pass"], base_url, session)
        time.sleep(random.uniform(5, 12))

if __name__ == "__main__":
    main()
