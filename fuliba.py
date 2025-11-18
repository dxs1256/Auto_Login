#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import re
import os
import time
import random

# ==================== 配置 ====================
PROXY = os.getenv("SOCKS5_PROXY")
if not PROXY:
    raise Exception("未设置 SOCKS5_PROXY")
proxies = {"http": f"socks5://{PROXY}", "https": f"socks5://{PROXY}"}

ACCOUNTS = [{"user": p.split(":")[0], "pass": p.split(":")[1]} 
            for p in os.getenv("WNFLB_USERS", "").split("|||") if ":" in p]

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID   = os.getenv("TG_CHAT_ID")

DOMAINS = ["https://www.wnflb2023.com","https://www.wnflb2024.com","https://www.wnflb2025.com"]

def tg(msg):
    if TG_BOT_TOKEN and TG_CHAT_ID:
        try:
            requests.post(f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
                          data={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
        except: pass

def sign_and_report(user, pwd):
    s = requests.Session()
    s.proxies.update(proxies)
    base = next((d for d in DOMAINS if s.get(d+"/forum.php", timeout=12).ok), None)
    if not base: return "所有域名失联"

    try:
        # 1. 登录
        html = s.get(base + "/forum.php").text
        formhash = re.search(r'formhash" value="(\w{8})"', html).group(1)
        s.post(base + "/member.php?mod=logging&action=login&loginsubmit=yes&inajax=1",
               data={"formhash":formhash,"username":user,"password":pwd,"cookietime":2592000},
               headers={"X-Requested-With":"XMLHttpRequest"}, timeout=12)

        # 2. 签到 + 奖励
        resp = s.get(base + "/plugin.php?id=fx_checkin:checkin").text
        if "已签到" in resp or "今日已经签到" in resp:
            already = True
        else:
            already = False
            reward = re.search(r"获得\s*([\d,]+)\s*威望", resp)
            reward = reward.group(1).replace(",", "") if reward else "?"

        # 3. 今天第几名 + 时间（ajax接口）
        today = time.strftime("%d").lstrip("0")
        ajax = s.get(base + f"/plugin.php?id=fx_checkin:ajax&date={time.strftime('%Y%m')}&inajax=1").text
        rank_match = re.search(fr'"{int(today)}".*?"l":(\d+)', ajax)
        rank = rank_match.group(1) if rank_match else "?"

        # 4. 连签、累计、个人排名（list接口）
        list_html = s.get(base + "/plugin.php?id=fx_checkin:list").text
        streak = re.search(r"连签\D*(\d+)天", list_html)
        total  = re.search(r"累计\D*(\d+)天", list_html)
        personal_rank = re.search(r"个人排名\D*(\d+)", list_html)

        streak = streak.group(1) if streak else "?"
        total  = total.group(1) if total else "?"
        personal_rank = personal_rank.group(1) if personal_rank else "?"

        # 5. 组装最终消息
        lines = [f"用户 <b>{user}</b>"]
        if already:
            lines.append("✅ 今天已经签到过了")
        else:
            lines.append(f"🎉 签到成功！获得 <b>{reward}</b> 威望")

        lines += [
            f"🏆 今天第 <b>{rank}</b> 名签到",
            f"🔥 连签 <b>{streak}</b> 天｜累计 <b>{total}</b> 天",
            f"👤 个人排名第 <b>{personal_rank}</b> 位"
        ]
        return "\n".join(lines)

    except Exception as e:
        return f"❌ 出错：{str(e)}"

def main():
    results = []
    for a in ACCOUNTS:
        results.append(sign_and_report(a["user"], a["pass"]))
        time.sleep(random.uniform(12, 22))

    bj_time = time.strftime('%Y-%m-%d %H:%M', time.gmtime(time.time() + 28800))
    final = "\n\n".join(results) + f"\n\n{bj_time} 北京时间"

    print(final)
    tg(final)

if __name__ == "__main__":
    main()
