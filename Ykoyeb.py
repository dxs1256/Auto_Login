import os
import json
import time
import logging
import requests
from datetime import datetime, timedelta

# 配置日志格式
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def validate_env_variables():
    """验证环境变量"""
    koyeb_accounts_env = os.getenv("KOYEB_ACCOUNTS")
    if not koyeb_accounts_env:
        raise ValueError("❌ KOYEB_ACCOUNTS 环境变量未设置或格式错误")
    try:
        return json.loads(koyeb_accounts_env)
    except json.JSONDecodeError:
        raise ValueError("❌ KOYEB_ACCOUNTS JSON 格式无效")

def send_tg_message(message):
    """发送 Telegram 消息"""
    bot_token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")

    if not bot_token or not chat_id:
        logging.warning("⚠️ TG_BOT_TOKEN 或 TG_CHAT_ID 未设置，跳过 Telegram 通知")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}

    try:
        response = requests.post(url, data=data, timeout=30)
        response.raise_for_status()
        logging.info("✅ Telegram 消息发送成功")
    except requests.RequestException as e:
        logging.error(f"❌ 发送 Telegram 消息失败: {e}")

def login_koyeb(email, password):
    """执行 Koyeb 账户登录"""
    if not email or not password:
        return False, "邮箱或密码为空"

    login_url = "https://app.koyeb.com/v1/account/login"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    data = {"email": email.strip(), "password": password}

    try:
        response = requests.post(login_url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        return True, "成功"
    except requests.Timeout:
        return False, "请求超时"
    except requests.RequestException as e:
        return False, str(e)

def main():
    """主流程"""
    try:
        koyeb_accounts = validate_env_variables()
        if not koyeb_accounts:
            raise ValueError("❌ 没有找到有效的 Koyeb 账户信息")

        # 获取北京时间（UTC+8）
        current_time = (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
        messages = []

        for account in koyeb_accounts:
            email = account.get("email", "").strip()
            password = account.get("password", "")

            if not email or not password:
                logging.warning(f"⚠️ 账户信息不完整，跳过: {email}")
                continue

            logging.info(f"🔄 正在处理账户: {email}")
            success, message = login_koyeb(email, password)

            result = "🎉 登录结果: 成功" if success else f"❌ 登录失败 | 原因: {message}"
            messages.append(f"📧 账户: {email}\n\n{result}")

            time.sleep(5)

        summary = f"🗓️ 北京时间: {current_time}\n\n" + "\n\n".join(messages) + "\n\n✅ Koyeb 登录成功"

        logging.info("📋 任务完成，发送 Telegram 通知")
        send_tg_message(summary)

    except Exception as e:
        error_message = f"❌ 执行出错: {e}"
        logging.error(error_message)
        send_tg_message(error_message)

if __name__ == "__main__":
    main()
