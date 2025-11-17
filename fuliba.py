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
from bs4 import BeautifulSoup
import time 

# --- 可配置参数 ---
FUBA_DOMAINS = ['www.wnflb2023.com', 'www.wnflb00.com', 'www.wnflb99.com']
FORUM_PATH = '/forum.php?mobile=no'

# --- 通知配置（从环境变量获取）---
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
WECOM_WEBHOOK = os.getenv("WECOM_WEBHOOK")  # 👈 新增：企业微信 webhook 地址

# --------------------------------

def send_telegram_notification(title, message):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("⚠️ Telegram Token 或 Chat ID 未配置，跳过发送通知。")
        return

    now_utc8 = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    time_str = now_utc8.strftime('%Y-%m-%d %H:%M:%S')

    full_message = f"🎉 **{title}**\n\n🕒 **运行时间：**{time_str}\n\n{message}"

    try:
        telegram_url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TG_CHAT_ID,
            'text': full_message,
            'parse_mode': 'Markdown'
        }
        response = requests.post(telegram_url, json=payload, timeout=10)
        response.raise_for_status()
        print("✅ Telegram 通知发送成功")
    except Exception as e:
        print(f"❌ Telegram 通知发送失败: {e}")


# 👇 新增：企业微信通知函数（支持 Markdown）
def send_wecom_notification(title, message):
    """
    通过企业微信机器人发送 Markdown 通知。
    """
    if not WECOM_WEBHOOK:
        print("⚠️ 企业微信 Webhook 未配置，跳过发送通知。")
        return

    now_utc8 = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    time_str = now_utc8.strftime('%Y-%m-%d %H:%M:%S')

    # 构建 Markdown 内容（企业微信支持部分 Markdown）
    content = f"""# 🎉 {title}

🕒 **运行时间**：{time_str}

{message}"""

    # 截断至 4096 字节（企业微信限制）
    # 注意：需按 UTF-8 字节长度判断
    while len(content.encode('utf-8')) > 4096:
        content = content[:-1]  # 逐字删减（或更智能地截断）

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": content
        }
    }

    try:
        headers = {"Content-Type": "application/json; charset=utf-8"}
        response = requests.post(WECOM_WEBHOOK, json=payload, headers=headers, timeout=10)
        res_json = response.json()
        if res_json.get("errcode") == 0:
            print("✅ 企业微信通知发送成功")
        else:
            print(f"❌ 企业微信通知发送失败: {res_json}")
    except Exception as e:
        print(f"❌ 企业微信通知异常: {e}")


def start(cookie, username):
    if not cookie:
        raise ValueError("【福利吧】未配置Cookie，请设置环境变量 FUBA")
    if not username:
        raise ValueError("【福利吧】未配置用户名，请设置环境变量 FUBAUN")

    session = requests.session()
    flb_url = None
    
    print("🚀 开始探测福利吧可用域名...")
    for domain in FUBA_DOMAINS:
        try:
            response = session.get(f"https://{domain}", timeout=10)
            if response.status_code == 200:
                flb_url = domain
                print(f"✅ 探测到可用域名: {flb_url}")
                break
        except requests.exceptions.RequestException:
            continue
    
    if not flb_url:
        raise Exception(f"【福利吧】未找到可用域名，请检查域名列表。")

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Host': flb_url,
        'Cookie': cookie,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    }

    forum_url = f'https://{flb_url}{FORUM_PATH}'
    print(f"🌐 访问主页: {forum_url}")
    try:
        response = session.get(forum_url, headers=headers, timeout=15)
        response.raise_for_status() 
        user_info_html = response.text
    except requests.exceptions.RequestException as e:
        raise Exception(f"【福利吧】访问主页失败: {e}")

    soup = BeautifulSoup(user_info_html, 'html.parser')
    current_logged_in_user_tag = soup.select_one('a[title="访问我的空间"]')
    current_user_name = current_logged_in_user_tag.text.strip() if current_logged_in_user_tag else "N/A"
    
    if current_user_name != username:
        raise Exception(f"【福利吧】**Cookie可能失效或用户名不匹配！**\n环境用户名: `{username}`\n页面用户名: `{current_user_name}`")
    
    print(f"✅ Cookie有效，用户 **{current_user_name}** 登录状态正常。")

    print("🔍 正在解析签到链接...")
    qiandao_path = None
    
    script_tag_with_checkin = soup.find('script', string=re.compile(r'fx_checkin\(.*?\)'))
    if script_tag_with_checkin:
        match = re.search(r'fx_checkin\s*\(\s*["\'](.*?plugin\.php\?id=fx_checkin[^"\']*)["\']', script_tag_with_checkin.string)
        if match:
            qiandao_path = match.group(1).strip().replace('&amp;', '&')
            print(f"✅ 成功解析到签到路径片段。")

    if not qiandao_path:
        qiandao_path = '/plugin.php?id=fx_checkin:ajax&inajax=1'
    
    today_date_str = datetime.datetime.now().strftime('%Y%m%d')
    if 'date=' not in qiandao_path:
        qiandao_path = f"{qiandao_path}&date={today_date_str}"
    if '_r=' not in qiandao_path:
        qiandao_path = f"{qiandao_path}&_r={int(datetime.datetime.now().timestamp() * 1000)}"

    full_qiandao_url = f'https://{flb_url}/{qiandao_path.lstrip("/")}'
    print(f"💪 准备签到，签到URL: {full_qiandao_url}")

    sign_status_message = ""
    try:
        response = session.get(full_qiandao_url, headers=headers, timeout=15)
        response.raise_for_status()
        sign_result_text = response.text
        print(f"📥 签到请求响应: {sign_result_text.strip()}")
        
        if "恭喜您" in sign_result_text or "获得" in sign_result_text:
            sign_status_message = "✅ 签到成功！"
        elif "今日已签" in sign_result_text or "已经签到" in sign_result_text:
            sign_status_message = "✅ 今日已签到（重复签到）。"
        elif '<root><![CDATA[]]></root>' in sign_result_text.strip():
            sign_status_message = "✅ 签到操作已执行（空响应）。"
        elif "Access Denied" in sign_result_text:
            sign_status_message = "❌ 签到失败: Access Denied，可能需要更新Cookie。"
        else:
            sign_status_message = f"❓ 签到响应不明确。**片段:** {sign_result_text.strip()[:100]}..."
        print(sign_status_message)

    except requests.exceptions.RequestException as e:
        sign_status_message = f"❌ 执行签到请求失败: {e}"

    time.sleep(1)
    log_info = ""
    try:
        response = session.get(forum_url, headers=headers, timeout=15)
        response.raise_for_status()
        soup_after_checkin = BeautifulSoup(response.text, 'html.parser')

        current_money_tag = soup_after_checkin.select_one('a[id="extcreditmenu"]')
        current_money = current_money_tag.text.strip() if current_money_tag else "未知积分"
        
        sign_day_tag = soup_after_checkin.select_one('div.tip_c')
        sign_day = sign_day_tag.text.strip() if sign_day_tag else "未知签到天数"
        
        log_info = (
            f"👤 **用户:** {username}\n"
            f"✅ **签到状态:** {sign_status_message}\n"
            f"🗓️ **{sign_day}**\n"
            f"💰 **当前积分:** {current_money}"
        )
    except requests.exceptions.RequestException as e:
        log_info = f"签到操作状态: {sign_status_message}\n⚠️ 获取最新积分失败: {e}"

    print(f"🎉 最终结果:\n{log_info}")

    # 👇 同时发送两个通知（可按需注释其中一个）
    send_telegram_notification("福利吧签到通知", log_info)
    send_wecom_notification("福利吧签到通知", log_info)  # 新增调用

    print("✅ 签到任务完成。")


if __name__ == '__main__':
    try:
        cookie_env = os.getenv("FUBA")
        username_env = os.getenv("FUBAUN")
        start(cookie_env, username_env)
    except Exception as e:
        error_message = f"【福利吧】脚本运行异常: {e}"
        print(f"❌ {error_message}")
        send_telegram_notification("福利吧签到失败", error_message)
        send_wecom_notification("福利吧签到失败", error_message)  # 新增调用

        sys.exit(1)