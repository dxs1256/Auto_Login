#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import os
import time
import random
import json   # 新增：用于安全发送 Telegram

# ==================== 从环境变量读取账号 ====================
WNFLB_USERS = os.getenv("WNFLB_USERS", "")
if WNFLB_USERS:
    pairs = [x.strip() for x in WNFLB_USERS.split("|||") if x.strip()]
    ACCOUNTS = [{"user": p.split(":")[0], "pass": p.split(":")[1]} for p in pairs]
else:
    ACCOUNTS = [{"user": os.getenv("WNFLB_USERNAME", ""), "pass": os.getenv("WNFLB_PASSWORD", "")}]

# ==================== Telegram 配置（可选） ====================
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")   # 你的 bot token
TG_CHAT_ID   = os.getenv("TG_CHAT_ID", "")     # 你的聊天 ID

def send_telegram(message):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, data=payload, timeout=10)
    except:
        pass  # 失败就失败吧，不影响主流程

# ==================== 域名轮询 ====================
DOMAINS = [
    "https://www.wnflb2023.com",
    "https://www.wnflb2024.com",
    "https://www.wnflb2025.com",
    "https://www.wnflb2026.com",
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

# ==================== 核心签到函数（提取威望并推 Telegram） ====================
def direct_sign(user, password, base_url, session):
    sign_api = f"{base_url}/plugin.php?id=fx_checkin:checkin"

    # 伪造最简登录态（fx_checkin 只认这两个 cookie）
    session.cookies.set("discuz_user", f"{user}^{password}")
    session.cookies.set("discuz_auth", "whatever")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": f"{base_url}/forum.php",
    }

    r = session.get(sign_api, headers=headers, timeout=10)
    text = r.text

    # 1. 已经签到过了
    if "今日已经签到" in text or "已签到" in text:
        msg = f"✅ {user} 今天已经签到过了"
        print(msg)
        send_telegram(msg)
        return True

    # 2. 签到成功 → 提取威望数值（支持多种返回文案）
    import re
    reward_match = re.search(r"获得\s*([\d,]+)\s*威望", text)
    if reward_match:
        reward = reward_match.group(1).replace(",", "")
        msg = f"🎉 {user} 签到成功！获得 <b>{reward}</b> 威望"
        print(msg)
        send_telegram(msg)
        return True

    # 3. 其他情况（基本不会走到这）
    print(f"[-] {user} 签到失败或返回异常")
    print(text[:400])
    send_telegram(f"❌ {user} 签到失败，请检查")
    return False

# ==================== 主函数 ====================
def main():
    # 每日整体通知（可选）
    send_telegram("⏰ 福利吧签到任务开始执行...")

    base_url, session = get_work_domain()
    success_count = 0

    for acc in ACCOUNTS:
        if not acc["user"] or not acc["pass"]:
            continue
        print(f"\n正在为 {acc['user']} 签到...")
        if direct_sign(acc["user"], acc["pass"], base_url, session):
            success_count += 1
        time.sleep(random.uniform(6, 15))

    # 任务总结
    summary = f"✅ 福利吧签到任务完成！成功 {success_count}/{len(ACCOUNTS)} 个账号\n{time.strftime('%Y-%m-%d %H:%M')} 北京时间"
    print(summary)
    send_telegram(summary)

if __name__ == "__main__":
    main()
