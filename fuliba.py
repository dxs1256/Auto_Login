#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
福利吧（wnflb2023/2024/2025...）自动签到 Python 版
作者：基于无数前辈的经验总结
适用所有使用 fx_checkin 签到插件的福利吧马甲站
"""

import requests
import re
import time
import random
from urllib3.util import Retry
from requests.adapters import HTTPAdapter

# ==================== 请在这里填写你的账号密码 ====================
USERNAME = "你的用户名"      # 改成你的
PASSWORD = "你的密码"        # 改成你的（明文，没事，本地运行）
# =================================================================

# 如果你想支持多个账号签到，可以改成列表循环
ACCOUNTS = [
    # {"user": "user1", "pass": "pass1"},
    # {"user": "user2", "pass": "pass2"},
    {"user": USERNAME, "pass": PASSWORD},
]

# 常见福利吧域名（被封一个换下一个，程序会自动尝试）
DOMAINS = [
    "https://www.wnflb2023.com",
    "https://www.wnflb2024.com",
    "https://www.wnflb2025.com",
    "https://www.wnflb2026.com",  # 预留未来
    "https://wnflb.org",
    "https://wnflb.co",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Referer": "https://www.wnflb2023.com/forum.php",
    "Origin": "https://www.wnflb2023.com",
}

def get_work_domain(session):
    """轮流尝试域名，直到找到活的"""
    for domain in DOMAINS:
        try:
            resp = session.get(domain + "/forum.php", timeout=10)
            if resp.status_code == 200 and "福利吧" in resp.text:
                print(f"[+] 找到可用域名: {domain}")
                return domain
        except:
            continue
    raise Exception("所有域名都挂了，福利吧可能凉了...")

def login(session, base_url, username, password):
    login_url = f"{base_url}/member.php?mod=logging&action=login&loginsubmit=yes&inajax=1"
    
    # 先获取 formhash
    resp = session.get(f"{base_url}/forum.php")
    formhash = re.search(r'name="formhash" value="([^"]+)"', resp.text)
    if not formhash:
        raise Exception("获取 formhash 失败，可能页面结构变了")
    formhash = formhash.group(1)

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
        print(resp.text)
        return False

def sign_in(session, base_url):
    # fx_checkin 签到链接通常是这个（所有福利吧都一样）
    sign_url = f"{base_url}/plugin.php?id=fx_checkin:checkin"
    
    try:
        resp = session.get(sign_url, timeout=10)
        if "已签到" in resp.text or "今日已经签到" in resp.text:
            print("[+] 今天已经签过了")
            return True
        elif "签到成功" in resp.text or "恭喜你签到成功" in resp.text:
            # 提取获得的积分
            reward = re.search(r"获得([^ ]+)威望", resp.text)
            if reward:
                print(f"[+] 签到成功！{reward.group(0)}")
            else:
                print("[+] 签到成功！")
            return True
        else:
            print("[-] 签到失败，页面返回异常")
            print(resp.text[:500])
            return False
    except Exception as e:
        print(f"[-] 签到请求异常: {e}")
        return False

def main():
    session = requests.Session()
    
    # 提高重试次数，网络不稳也能扛住
    retry = Retry(total=3, backoff_factor=1)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(HEADERS)

    for account in ACCOUNTS:
        username = account["user"]
        password = account["pass"]
        print(f"\n正在为 {username} 签到...")
        
        try:
            base_url = get_work_domain(session)
            if login(session, base_url, username, password):
                sign_in(session, base_url)
            time.sleep(random.uniform(3, 8))  # 防检测，随机延时
        except Exception as e:
            print(f"[-] 签到失败: {e}")
        
        # 每个账号结束后清一下 cookie，防止串号
        session.cookies.clear()

if __name__ == "__main__":
    main()
