#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import re
import os
import time
import random

# ==================== 代理（从 Secrets 读取） ====================
PROXY = os.getenv("SOCKS5_PROXY", "")
if not PROXY:
    raise Exception("未设置 SOCKS5_PROXY 环境变量！")
proxies = {"http": f"socks5://{PROXY}", "https": f"socks5://{PROXY}"}

# ==================== 账号（支持多账号） ====================
WNFLB_USERS = os.getenv("WNFLB_USERS", "")
if WNFLB_USERS:
    pairs = [x.strip() for x in WNFLB_USERS.split("|||") if x.strip()]
    ACCOUNTS = [{"user": p.split(":")[0], "pass": p.split(":")[1]} for p in pairs]
else:
    ACCOUNTS = [{"user": os.getenv("WNFLB_USERNAME", ""), "pass": os.getenv("WNFLB_PASSWORD", "")}]

# ==================== Telegram 配置 ====================
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_CHAT_ID   = os.getenv("TG_CHAT_ID", "")

def send_tg(msg):
    if TG_BOT_TOKEN and TG_CHAT_ID:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
                data={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "HTML"},
                timeout=10
            )
        except:
            pass

# ==================== 域名轮询 ====================
DOMAINS = [
    "https://www.wnflb2023.com","https://www.wnflb2024.com","https://www.wnflb2025.com",
    "https://www.wnflb00.com","https://www.wnflb99.com"
]

def get_live_domain():
    s = requests.Session()
    s.proxies.update(proxies)
    s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
    for d in DOMAINS:
        try:
            r = s.get(d + "/forum.php", timeout=15)
            if r.status_code == 200 and "福利吧" in r.text:
                print(f"[+] 可用域名: {d}")
                return d.rstrip("/"), s
        except: continue
    raise Exception("全部域名挂了")

# ==================== 登录+签到（只返回状态文字） ====================
def login_and_sign(user, pwd, base_url, session):
    try:
        r = session.get(f"{base_url}/forum.php", timeout=15)
        formhash = re.search(r'name="formhash" value="([a-f0-9]{8})"', r.text)
        if not formhash:
            return "❌ 获取 formhash 失败"

        login_url = f"{base_url}/member.php?mod=logging&action=login&loginsubmit=yes&inajax=1"
        data = {
            "formhash": formhash.group(1),
            "referer": f"{base_url}/forum.php",
            "loginfield": "username",
            "username": user,
            "password": pwd,
            "questionid": "0",
            "answer": "",
            "cookietime": "2592000"
        }
        r = session.post(login_url, data=data, headers={"X-Requested-With": "XMLHttpRequest"}, timeout=15)
        if "欢迎您回来" not in r.text and "succeedhandle" not in r.text:
            return "❌ 登录失败（可能密码错或代理问题）"

        r = session.get(f"{base_url}/plugin.php?id=fx_checkin:checkin", timeout=15)
        text = r.text

        if "今日已经签到" in text or "已签到" in text:
            return "✅ 今天已经签到过了"
        elif "签到成功" in text or "获得" in text:
            reward = re.search(r"获得\s*([\d,]+)\s*威望", text)
            reward = reward.group(1).replace(",", "") if reward else "?"
            return f"🎉 签到成功！获得 <b>{reward}</b> 威望"
        else:
            return "❌ 签到失败（未知返回）"
    except Exception as e:
        return f"❌ 异常: {str(e)}"

# ==================== 主程序（每天只发一条消息） ====================
def main():
    base_url, session = get_live_domain()
    status_lines = []
    success = 0

    for acc in ACCOUNTS:
        if not acc["user"]: continue
        result = login_and_sign(acc["user"], acc["pass"], base_url, session)
        print(result)
        status_lines.append(result)
        if "成功" in result or "已经签到" in result:
            success += 1
        time.sleep(random.uniform(10, 20))

    # 北京时间（零依赖，GitHub Actions 必备）
    bj_time = time.strftime('%Y-%m-%d %H:%M', time.gmtime(time.time() + 28800))

    final_message = f"""⏰ 福利吧每日签到报告

{' '.join(status_lines)}

✅ 全部完成！成功 {success}/{len(ACCOUNTS)} 个账号
{bj_time} 北京时间"""

    print(final_message)
    send_tg(final_message)

if __name__ == "__main__":
    main()
