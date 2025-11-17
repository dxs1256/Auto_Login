# -*- coding: utf8 -*-
"""
cron: 0 0 2,6 * * *
new Env('福利吧签到');
"""

import requests
import re
import os
import sys
import datetime
import json
from bs4 import BeautifulSoup
import time 

# --- 可配置参数 ---
FUBA_DOMAINS = ['www.wnflb2023.com', 'www.wnflb00.com', 'www.wnflb99.com']
FORUM_PATH = '/forum.php?mobile=no'

# --- 通知配置（从环境变量加载）---
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "").strip()
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "").strip()
WECOM_WEBHOOK = os.getenv("WECOM_WEBHOOK", "").strip()

# 是否在企业微信中 @所有人（设为 False 则不提醒）
WECOM_MENTION_ALL = True

# --------------------------------

def send_telegram_notification(title, message):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("⚠️ Telegram 未配置，跳过通知")
        return False

    now_utc8 = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    time_str = now_utc8.strftime('%Y-%m-%d %H:%M:%S')
    full_message = f"🎉 **{title}**\n\n🕒 **运行时间：**{time_str}\n\n{message}"

    try:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        payload = {'chat_id': TG_CHAT_ID, 'text': full_message, 'parse_mode': 'Markdown'}
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        print("✅ Telegram 通知发送成功")
        return True
    except Exception as e:
        print(f"❌ Telegram 通知失败: {e}")
        return False


def send_wecom_notification(title, message):
    """
    发送企业微信文本通知（严格遵循官方限制）
    - msgtype: text
    - content ≤ 2048 bytes (UTF-8)
    - 支持 mentioned_list: ["@all"]
    """
    if not WECOM_WEBHOOK:
        print("⚠️ WECOM_WEBHOOK 未配置，跳过企业微信通知")
        return False

    # 构造消息内容
    now_utc8 = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    time_str = now_utc8.strftime('%Y-%m-%d %H:%M:%S')
    content = f"【{title}】\n🕒 {time_str}\n\n{message}"

    # 严格截断至 2048 字节（UTF-8）
    while len(content.encode('utf-8')) > 2048:
        content = content[:-1]

    payload = {
        "msgtype": "text",
        "text": {
            "content": content
        }
    }

    # 可选：添加 @all
    if WECOM_MENTION_ALL:
        payload["text"]["mentioned_list"] = ["@all"]

    try:
        print(f"📤 发送企业微信通知（text 类型），长度: {len(content.encode('utf-8'))} 字节")
        print(f"📝 内容预览: {repr(content[:100])}...")

        resp = requests.post(
            WECOM_WEBHOOK,
            json=payload,
            headers={'Content-Type': 'application/json; charset=utf-8'},
            timeout=10
        )
        print(f"📡 HTTP {resp.status_code}, 响应: {resp.text}")

        res = resp.json()
        if res.get("errcode") == 0:
            print("✅ 企业微信通知发送成功！")
            return True
        else:
            print(f"❌ 企业微信返回错误: errcode={res.get('errcode')}, errmsg={res.get('errmsg')}")
            return False
    except Exception as e:
        print(f"💥 企业微信通知异常: {e}")
        return False


def start(cookie, username):
    if not cookie:
        raise ValueError("【福利吧】未配置 Cookie，请设置环境变量 FUBA")
    if not username:
        raise ValueError("【福利吧】未配置用户名，请设置环境变量 FUBAUN")

    session = requests.Session()
    flb_url = None

    print("🚀 开始探测福利吧可用域名...")
    for domain in FUBA_DOMAINS:
        try:
            resp = session.get(f"https://{domain}", timeout=10)
            if resp.status_code == 200:
                flb_url = domain
                print(f"✅ 探测到可用域名: {flb_url}")
                break
        except Exception as e:
            print(f"❌ 域名 {domain} 不可达: {e}")
            continue

    if not flb_url:
        raise Exception("【福利吧】所有域名均不可用，请检查网络或域名列表")

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Host': flb_url,
        'Cookie': cookie,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    }

    forum_url = f'https://{flb_url}{FORUM_PATH}'
    print(f"🌐 访问主页: {forum_url}")
    try:
        resp = session.get(forum_url, headers=headers, timeout=15)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        raise Exception(f"【福利吧】访问主页失败: {e}")

    soup = BeautifulSoup(html, 'html.parser')
    user_tag = soup.select_one('a[title="访问我的空间"]')
    current_user = user_tag.text.strip() if user_tag else "N/A"

    if current_user != username:
        raise Exception(f"【福利吧】Cookie 失效或用户名不匹配！\n期望: {username}，实际: {current_user}")

    print(f"✅ 用户 {current_user} 登录状态正常")

    # 解析签到链接
    print("🔍 解析签到链接...")
    qiandao_path = None
    script = soup.find('script', string=re.compile(r'fx_checkin'))
    if script:
        m = re.search(r'fx_checkin\s*\(\s*["\'](.*?id=fx_checkin[^"\']*)["\']', script.string)
        if m:
            qiandao_path = m.group(1).replace('&amp;', '&')
            print("✅ 动态解析签到路径成功")

    if not qiandao_path:
        qiandao_path = '/plugin.php?id=fx_checkin:ajax&inajax=1'
        print("🟡 使用默认签到路径")

    # 补充动态参数
    today = datetime.datetime.now().strftime('%Y%m%d')
    if 'date=' not in qiandao_path:
        qiandao_path += f"&date={today}"
    if '_r=' not in qiandao_path:
        qiandao_path += f"&_r={int(time.time() * 1000)}"

    full_url = f'https://{flb_url}/{qiandao_path.lstrip("/")}'
    print(f"💪 签到 URL: {full_url}")

    # 执行签到
    sign_msg = ""
    try:
        resp = session.get(full_url, headers=headers, timeout=15)
        resp.raise_for_status()
        text = resp.text.strip()
        print(f"📥 响应: {repr(text[:200])}")

        if "恭喜您" in text or "获得" in text:
            sign_msg = "✅ 签到成功！"
        elif "今日已签" in text or "已经签到" in text:
            sign_msg = "✅ 今日已签到（重复签到）"
        elif '<root><![CDATA[]]></root>' in text:
            sign_msg = "✅ 签到成功（空响应）"
        elif "Access Denied" in text:
            sign_msg = "❌ 签到失败：Access Denied（Cookie 可能过期）"
        else:
            sign_msg = f"❓ 响应不明确（片段）：{text[:100]}"
        print(sign_msg)

    except Exception as e:
        sign_msg = f"❌ 签到请求失败: {e}"

    # 获取积分
    time.sleep(1)
    log_info = ""
    try:
        resp = session.get(forum_url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup2 = BeautifulSoup(resp.text, 'html.parser')

        money_tag = soup2.select_one('a[id="extcreditmenu"]')
        money = money_tag.text.strip() if money_tag else "未知"

        day_tag = soup2.select_one('div.tip_c')
        days = day_tag.text.strip() if day_tag else "未知"

        log_info = (
            f"👤 用户: {username}\n"
            f"✅ 状态: {sign_msg}\n"
            f"🗓️ {days}\n"
            f"💰 积分: {money}"
        )
    except Exception as e:
        log_info = f"签到状态: {sign_msg}\n⚠️ 积分获取失败: {e}"

    print(f"\n🎉 最终结果:\n{log_info}")

    # 👇 同时发送双通道通知
    send_telegram_notification("福利吧签到通知", log_info)
    send_wecom_notification("福利吧签到通知", log_info)

    print("✅ 签到任务完成")


if __name__ == '__main__':
    try:
        # 调试：打印环境变量
        print(f"🔧 WECOM_WEBHOOK 配置: {'✅ 已设置' if WECOM_WEBHOOK else '❌ 未设置'}")
        print(f"🔧 TG 配置: {'✅' if TG_BOT_TOKEN and TG_CHAT_ID else '❌'}")

        cookie = os.getenv("FUBA", "").strip()
        username = os.getenv("FUBAUN", "").strip()
        start(cookie, username)

    except Exception as e:
        err_msg = f"【福利吧】脚本异常: {e}"
        print(f"❌ {err_msg}")

        send_telegram_notification("福利吧签到失败", err_msg)
        send_wecom_notification("福利吧签到失败", err_msg)

        sys.exit(1)
