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
    raise Exception("未设置 SOCKS5_PROXY 环境变量！")
proxies = {"http": f"socks5://{PROXY}", "https": f"socks5://{PROXY}"}

# 支持多账号 user:pass|||user2:pass2
ACCOUNTS = [
    {"user": p.split(":")[0], "pass": p.split(":")[1]}
    for p in os.getenv("WNFLB_USERS", "").split("|||") if ":" in p
]

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID   = os.getenv("TG_CHAT_ID")

DOMAINS = [
    "https://www.wnflb2023.com",
    "https://www.wnflb2024.com",
    "https://www.wnflb2025.com"
]

# ==================== Telegram 推送 ====================
def tg(msg):
    if TG_BOT_TOKEN and TG_CHAT_ID:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
                data={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "HTML"},
                timeout=10
            )
        except:
            pass

# ==================== 核心签到+信息抓取 ====================
def sign_and_report(user, pwd):
    s = requests.Session()
    s.proxies.update(proxies)
    s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

    # 找活域名
    base = next((d for d in DOMAINS if s.get(d + "/forum.php", timeout=12).ok), None)
    if not base:
        return "❌ 所有域名失联"

    try:
        # 1. 登录
        html = s.get(f"{base}/forum.php", timeout=15).text
        formhash = re.search(r'name="formhash" value="(\w{8})"', html)
        if not formhash:
            return "❌ 获取 formhash 失败"
        formhash = formhash.group(1)

        s.post(
            f"{base}/member.php?mod=logging&action=login&loginsubmit=yes&inajax=1",
            data={
                "formhash": formhash,
                "username": user,
                "password": pwd,
                "cookietime": "2592000"
            },
            headers={"X-Requested-With": "XMLHttpRequest"},
            timeout=15
        )

        # 2. 签到结果
        checkin_resp = s.get(f"{base}/plugin.php?id=fx_checkin:checkin", timeout=15).text
        already_signed = "今日已经签到" in checkin_resp or "已签到" in checkin_resp
        reward = "?"
        if not already_signed and "签到成功" in checkin_resp:
            m = re.search(r"获得\s*([\d,]+)\s*威望", checkin_resp)
            reward = m.group(1).replace(",", "") if m else "?"

        # 3. 今天第几名
        ajax_resp = s.get(
            f"{base}/plugin.php?id=fx_checkin:ajax&date={time.strftime('%Y%m')}&inajax=1",
            timeout=15
        ).text
        rank = re.search(fr'"{int(time.strftime("%d"))}".*?"l":(\d+)', ajax_resp)
        rank = rank.group(1) if rank else "?"

        # 4. 连签、累计、个人排名 —— 超级稳的三重保险抓取
        list_html = s.get(f"{base}/plugin.php?id=fx_checkin:list", timeout=15).text

        # 保险1：优先精准定位包含用户名的 <tr>
        user_row = re.search(rf"{re.escape(user)}.*?(?=<tr|<div|$)", list_html, re.S | re.I)
        text_block = user_row.group(0) if user_row else list_html

        # 保险2：再从块里提取
        streak = re.search(r"连签\D*(\d+)", text_block)
        total  = re.search(r"累计\D*(\d+)", text_block)
        prank  = re.search(r"排名\D*(\d+)", text_block)

        # 保险3：如果上面没抓到，就全局再扫一遍（基本不可能走到这）
        if not streak:
            streak = re.search(r"连签\D*(\d+)", list_html)
        if not total:
            total = re.search(r"累计\D*(\d+)", list_html)
        if not prank:
            prank = re.search(r"排名\D*(\d+)", list_html)

        streak = streak.group(1) if streak else "?"
        total  = total.group(1) if total else "?"
        prank  = prank.group(1) if prank else "?"

        # 5. 组装消息
        lines = [f"用户 <b>{user}</b>"]
        if already_signed:
            lines.append("✅ 今天已经签到过了")
        else:
            lines.append(f"🎉 签到成功！获得 <b>{reward}</b> 威望")

        lines += [
            f"🏆 今天第 <b>{rank}</b> 名签到",
            f"🔥 连签 <b>{streak}</b> 天｜累计 <b>{total}</b> 天",
            f"👤 个人排名第 <b>{prank}</b> 位"
        ]
        return "\n".join(lines)

    except Exception as e:
        return f"❌ {user} 出错：{str(e)}"

# ==================== 主程序 ====================
def main():
    results = []
    for acc in ACCOUNTS:
        results.append(sign_and_report(acc["user"], acc["pass"]))
        time.sleep(random.uniform(12, 22))

    bj_time = time.strftime('%Y-%m-%d %H:%M', time.gmtime(time.time() + 28800))
    final_msg = "\n\n".join(results) + f"\n\n{bj_time} 北京时间"

    print(final_msg)
    tg(final_msg)

if __name__ == "__main__":
    main()
