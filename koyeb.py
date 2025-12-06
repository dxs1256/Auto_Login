import os
import json
import time
import logging
import requests
from datetime import datetime, timedelta

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def validate_env_variables():
    """验证并读取 KOYEB_TOKENS（支持单个字符串或 JSON 数组）"""
    koyeb_tokens_env = os.getenv("KOYEB_TOKENS")
    if not koyeb_tokens_env:
        raise ValueError("KOYEB_TOKENS 环境变量未设置")
    try:
        tokens = json.loads(koyeb_tokens_env)
        return tokens if isinstance(tokens, list) else [tokens]
    except json.JSONDecodeError:
        return [koyeb_tokens_env]  # 单个 token 时直接使用

def send_tg_message(message):
    """发送 Telegram 消息"""
    bot_token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    if not bot_token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=data, timeout=10)
        logging.info("Telegram 通知已发送")
    except Exception as e:
        logging.error(f"TG 发送失败: {e}")

def send_pushplus_message(message):
    """发送 PushPlus 消息"""
    token = os.getenv("PUSHPLUS_TOKEN")
    if not token:
        return
    url = "http://www.pushplus.plus/send"
    data = {
        "token": token,
        "title": "Koyeb 账户状态",
        "content": message,
        "template": "markdown"
    }
    try:
        requests.post(url, json=data, timeout=10)
        logging.info("PushPlus 通知已发送")
    except Exception as e:
        logging.error(f"PushPlus 发送失败: {e}")

def check_koyeb_activity(token):
    """检查 Koyeb 账户是否活跃"""
    url = "https://app.koyeb.com/v1/account/profile"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            email = data.get("user", {}).get("email", "未知邮箱")
            return True, email, response  # 返回 response 以便后续取 email
        elif response.status_code == 401:
            return False, "Token 无效或已过期", None
        else:
            return False, f"API 错误 {response.status_code}", None
    except requests.Timeout:
        return False, "请求超时", None
    except Exception as e:
        return False, f"网络异常：{str(e)}", None

def main():
    try:
        tokens = validate_env_variables()
        token = tokens[0]  # 你只有一个账号，直接取第一个
        masked_token = token[:6] + "****" + token[-4:] if len(token) > 10 else "****"

        logging.info("开始检查 Koyeb 账户状态...")
        
        success, result_msg, response = check_koyeb_activity(token)
        
        if success:
            # 成功时提取真实邮箱
            try:
                email = response.json().get("user", {}).get("email", "未知邮箱")
            except:
                email = "未知邮箱"
            
            summary = f"""Koyeb 账户状态

活跃正常
邮箱：{email}

一切正常，无需操作～
保持活跃中..."""
        else:
            summary = f"""Koyeb 账户状态

已失活或异常
掩码：{masked_token}
原因：{result_msg}

请尽快登录 Koyeb 后台重新生成 Token！"""

        # 发送通知
        send_tg_message(summary)
        send_pushplus_message(summary)
        logging.info("检查完成，通知已推送")

    except Exception as e:
        error_msg = f"""Koyeb 脚本执行失败

错误信息：{str(e)}

请检查环境变量或网络连接"""
        logging.error(error_msg)
        send_tg_message(error_msg)
        send_pushplus_message(error_msg)

if __name__ == "__main__":
    main()
