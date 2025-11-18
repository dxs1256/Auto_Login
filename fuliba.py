#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import re
import os
import time
import random

# ==================== 代理设置（填你的 SOCKS5） ====================
# 格式： username:password@ip:port   （没有账号密码就直接 ip:port）
import os
PROXY = os.getenv("SOCKS5_PROXY", "")   # 格式：username:password@ip:port

if not PROXY:
    raise Exception("未设置 SOCKS5_PROXY 环境变量！去 Secrets 加一个")

proxies = {
    "http":  f"socks5://{PROXY}",
    "https": f"socks5://{PROXY}"
}

# ==================== 账号读取 ====================
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
            requests.post(f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
                          data={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=15)
        except:
            pass

# ==================== 域名轮询 ====================
DOMAINS = [
    "https://www.wnflb2023.com",
    "https://www.wnflb2024.com",
    "https://www.wnflb2025.com",
    "https://www.wnflb00.com",
    "https://www.wnflb99.com",
]

def get_live_domain():
    s = requests.Session()
    s.proxies.update(proxies)        # ← 全局启用代理
    s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
    
    for d in DOMAINS:
        try:
            r = s.get(d + "/forum.php", timeout=15)
            if r.status_code == 200 and "福利吧" in r.text:
                print(f"[+] 可用域名: {d}")
                return d.rstrip("/"), s
        except Exception as e:
            print(f"[-] {d} 访问失败: {e}")
            continue
    raise Exception("全部域名都挂了")

# ==================== 登录 + 签到 ====================
def login_and_sign(user, pwd, base_url, session):
    try:
        r = session.get(f"{base_url}/forum.php", timeout=15)
        formhash_match = re.search(r'name="formhash" value="([a-f0-9]{8})"', r.text)
        if not formhash_match:
            send_tg(f"❌ {user} 获取 formhash 失败")
            return False
        formhash = formhash_match.group(1)

        login_url = f"{base_url}/member.php?mod=logging&action=login&loginsubmit=yes&inajax=1"
        data = {
            "formhash": formhash,
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
            send_tg(f"❌ {user} 登录失败（可能密码错或代理问题）\n{r.text[:200]}")
            return False

        # 签到
        r = session.get(f"{base_url}/plugin.php?id=fx_checkin:checkin", timeout=15)
        text = r.text

        if "今日已经签到" in text or "已签到" in text:
            msg = f"✅ {user} 今天已经签到过了"
        elif "签到成功" in text or "获得" in text:
            reward = re.search(r"获得\s*([\d,]+)\s*威望", text)
            reward = reward.group(1).replace(",", "") if reward else "?"
            msg = f"🎉 {user} 签到成功！获得 <b>{reward}</b> 威望"
        else:
            msg = f"❌ {user} 签到失败（未知返回）"
            print(text[:500])

        print(msg)
        send_tg(msg)
        return True

    except Exception as e:
        err = f"❌ {user} 异常: {str(e)}"
        print(err)
        send_tg(err)
        return False

# ==================== 主程序 ====================
# ==================== 主程序 ====================
def main():
    # send_tg("⏰ 福利吧签到任务开始（已启用 SOCKS5 代理）")   ← 删除这行
    base_url, session = get_live_domain()
    success = 0
    details = []   # ← 新增：用来收集每条账号的状态

    for acc in ACCOUNTS:
        if not acc["user"]: continue
        print(f"\n正在为 {acc['user']} 签到...")
        result = login_and_sign(acc["user"], acc["pass"], base_url, session)
        if result:
            success += 1
        # login_and_sign 里已经不发 Telegram 了，这里收集文字
        # （如果你之前 login_and_sign 里有 send_tg，也全删掉，只 print 就行）

    # 最终只发一条完整消息
    summary = f"""⏰ 福利吧每日签到报告

{' '.join(details)}

✅ 全部完成！成功 {success}/{len(ACCOUNTS)} 个账号
{time.strftime('%Y-%m-%d %H:%M')} 北京时间"""

    print(summary)
    send_tg(summary)   # ← 只剩这一条

if __name__ == "__main__":
    main()
