# -*- coding: utf8 -*-

"""
# 下方cron签到时间意思是：每天2点和6点签到一次，以防签到失败
cron: 0 0 2,6 * * *
new Env('福利吧签到');
"""

import requests
import re
import os
import sys
import datetime # 导入 datetime 模块
from bs4 import BeautifulSoup

# --- 可配置参数 ---
# 福利吧可能的域名列表，按优先级排序
FUBA_DOMAINS = ['www.wnflb2023.com', 'www.wnflb00.com', 'www.wnflb99.com']
# 登录页面和签到页面路径模式（通常是固定的）
FORUM_PATH = '/forum.php?mobile=no'
# --- 可配置参数结束 ---

# --- Telegram 通知配置 ---
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
# --- Telegram 通知配置结束 ---

def send_telegram_notification(title, message):
    """
    通过 Telegram Bot 发送通知。
    :param title: 通知标题。
    :param message: 通知内容。
    """
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("⚠️ Telegram Token 或 Chat ID 未配置，跳过发送通知。")
        return

    # 获取当前香港时间
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    time_str = now.strftime('%Y-%m-%d %H:%M:%S HKT')

    full_message = f"🎉 {title}\n\n登录时间：{time_str}\n\n{message}"

    try:
        telegram_url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TG_CHAT_ID,
            'text': full_message
        }
        response = requests.post(telegram_url, json=payload, timeout=10)
        response.raise_for_status()
        print("✅ Telegram 通知发送成功")
    except requests.exceptions.RequestException as e:
        print(f"❌ Telegram 通知发送失败: {e}")

def start(cookie, username):
    """
    执行福利吧签到任务。
    :param cookie: 用户登录Cookie字符串。
    :param username: 用户名，用于验证Cookie是否有效。
    """
    if not cookie:
        raise ValueError("【福利吧】未配置Cookie，请设置环境变量 FUBA")
    if not username:
        raise ValueError("【福利吧】未配置用户名，请设置环境变量 FUBAUN")

    session = requests.session()
    flb_url = None
    
    # 1. 探测可用域名
    print("🚀 开始探测福利吧可用域名...")
    for domain in FUBA_DOMAINS:
        temp_addr = "https://" + domain
        try:
            response = session.head(temp_addr, timeout=10) 
            if response.status_code == 200:
                flb_url = domain
                print(f"✅ 探测到可用域名: {flb_url}")
                break
        except requests.exceptions.RequestException as e:
            print(f"⚠️ 访问 {temp_addr} 失败: {e}")
    
    if not flb_url:
        raise Exception(f"【福利吧】未找到可用域名，请检查 {', '.join(FUBA_DOMAINS)} 是否可访问。")

    # 2. 构建请求头
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Cache-Control': 'max-age=0',
        'Upgrade-Insecure-Requests': '1',
        'Host': flb_url,
        'Cookie': cookie,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    }

    # 3. 访问主页并验证 Cookie
    print(f"🌐 访问主页: https://{flb_url}{FORUM_PATH}")
    try:
        response = session.get(f'https://{flb_url}{FORUM_PATH}', headers=headers, timeout=15)
        response.raise_for_status() # 检查 HTTP 错误
        user_info_html = response.text
    except requests.exceptions.RequestException as e:
        raise Exception(f"【福利吧】访问主页失败，可能网络问题或域名被墙: {e}")

    soup = BeautifulSoup(user_info_html, 'html.parser')
    
    # 尝试从页面中提取登录用户名 (更健壮的方式)
    current_logged_in_user_tag = soup.select_one('a[title="访问我的空间"]') # 假设有 title="访问我的空间"
    
    current_user_name = None
    if current_logged_in_user_tag:
        current_user_name = current_logged_in_user_tag.text.strip()
        print(f"✅ 从页面获取到登录用户名为: {current_user_name}")
    else:
        print("⚠️ 未通过'访问我的空间'获取到用户名，尝试其他方式。")
        user_center_tag = soup.select_one('a[href*="home.php?mod=space"]') # 匹配包含 home.php?mod=space 的a标签
        if user_center_tag:
             current_user_name = user_center_tag.text.strip()
             print(f"✅ 从用户中心链接获取到登录用户名为: {current_user_name}")

    if not current_user_name or current_user_name != username:
        raise Exception(f"【福利吧】Cookie可能失效或用户名不匹配！环境用户名: '{username}', 页面用户名: '{current_user_name}'")
    
    print(f"✅ Cookie有效，用户 '{current_user_name}' 登录状态正常。")

    # 4. 动态获取签到链接
    print("🔍 正在解析签到链接...")
    script_tag_with_checkin = soup.find('script', string=re.compile(r'fx_checkin\(.*?\)'))
    qiandao_path = None

    if script_tag_with_checkin:
        match = re.search(r'fx_checkin\(\'(.*?)\'\);', script_tag_with_checkin.string)
        if match:
            qiandao_path = match.group(1).strip()
            # 确保 URL 中包含日期和随机数，如果网站需要
            if 'date=' not in qiandao_path:
                # 获取当天的日期 YYYYMMDD
                today_date_str = datetime.datetime.now().strftime('%Y%m%d')
                qiandao_path = f"{qiandao_path}&date={today_date_str}"
            if '_r=' not in qiandao_path: # 添加随机数以避免缓存问题
                # 使用当前时间戳作为随机数的一部分，更简单且足够随机
                qiandao_path = f"{qiandao_path}&_r={int(datetime.datetime.now().timestamp() * 1000)}" 
            print(f"✅ 解析到签到路径: {qiandao_path}")
        else:
            print("⚠️ 未通过正则'fx_checkin('(...)');'提取到签到路径。")
    
    if not qiandao_path:
        print("⚠️ 未能从页面解析到签到路径，尝试使用默认路径。")
        # 这是一个常见的签到路径模式，如果网站有变更，可能需要手动更新此项
        qiandao_path = '/plugin.php?id=fx_checkin:ajax&inajax=1' 
        # 同样为默认路径添加动态日期和随机数
        if 'date=' not in qiandao_path:
            today_date_str = datetime.datetime.now().strftime('%Y%m%d')
            qiandao_path = f"{qiandao_path}&date={today_date_str}"
        if '_r=' not in qiandao_path:
            qiandao_path = f"{qiandao_path}&_r={int(datetime.datetime.now().timestamp() * 1000)}"

    full_qiandao_url = f'https://{flb_url}/{qiandao_path}'
    print(f"💪 准备签到，签到URL: {full_qiandao_url}")

    # 5. 执行签到
    sign_status_message = ""
    try:
        response = session.get(full_qiandao_url, headers=headers, timeout=15)
        response.raise_for_status()
        sign_result_text = response.text
        print(f"📥 签到请求响应: {sign_result_text.strip()}")
        
        if "恭喜您" in sign_result_text or "获得" in sign_result_text:
            sign_status_message = "✅ 签到成功！"
        elif "今日已签" in sign_result_text or "已经签到" in sign_result_text: # 增加已签到的判断
             sign_status_message = "✅ 今日已签到。"
        elif "Access Denied" in sign_result_text:
             sign_status_message = "❌ 签到失败: Access Denied，可能需要更新Cookie或IP问题。"
        else:
            sign_status_message = "❓ 签到响应不明确，请人工检查结果。"
        print(sign_status_message)

    except requests.exceptions.RequestException as e:
        raise Exception(f"【福利吧】执行签到请求失败: {e}")

    # 6. 获取并报告积分结果
    print("📊 正在获取签到结果和积分...")
    log_info = ""
    try:
        response = session.get(f'https://{flb_url}{FORUM_PATH}', headers=headers, timeout=15)
        response.raise_for_status()
        user_info_html_after_checkin = response.text
    except requests.exceptions.RequestException as e:
        log_info = f"签到操作完成，但获取最新积分失败: {e}"
        print(f"⚠️ {log_info}")
        send_telegram_notification("福利吧签到通知", f"用户: {username}\n{sign_status_message}\n{log_info}")
        return # 直接返回，不发送重复通知

    soup_after_checkin = BeautifulSoup(user_info_html_after_checkin, 'html.parser')

    current_money_tag = soup_after_checkin.select_one('a[id="extcreditmenu"]')
    current_money = current_money_tag.text.strip() if current_money_tag else "未知积分"
    
    sign_day_tag = soup_after_checkin.select_one('div.tip_c') 
    sign_day = sign_day_tag.text.strip() if sign_day_tag else "未知签到天数"
    
    log_info = f"用户: {username}\n{sign_status_message}\n{sign_day}\n当前: {current_money}"
    print(f"🎉 最终结果:\n{log_info}")
    send_telegram_notification("福利吧签到通知", log_info)

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
        sys.exit(1) # 脚本异常退出，让自动化平台知道失败
