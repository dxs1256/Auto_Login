import os
import json
import logging
import requests
from datetime import datetime, timedelta, timezone

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
        return [koyeb_tokens_env]

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
        "title": "Koyeb 账户状态报告",
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
            return True, email, response
        elif response.status_code == 401:
            return False, "Token 无效或已过期", None
        else:
            return False, f"API 错误 {response.status_code}", None
    except requests.Timeout:
        return False, "请求超时", None
    except Exception as e:
        return False, f"网络异常：{str(e)}", None

def get_beijing_time():
    """获取北京时间字符串"""
    # 获取 UTC 时间并加 8 小时
    utc_now = datetime.now(timezone.utc)
    beijing_now = utc_now + timedelta(hours=8)
    return beijing_now.strftime("%Y-%m-%d %H:%M:%S")

def main():
    try:
        tokens = validate_env_variables()
        token = tokens[0]
        masked_token = token[:6] + "****" + token[-4:] if len(token) > 10 else "****"
        
        # 获取北京时间
        current_time = get_beijing_time()

        logging.info("开始检查 Koyeb 账户状态...")
        
        success, result_msg, response = check_koyeb_activity(token)
        
        if success:
            try:
                email = response.json().get("user", {}).get("email", "未知邮箱")
            except:
                email = "未知邮箱"
            
            # --- 成功通知 (无加粗, 北京时间) ---
            summary = (
                "☁️ Koyeb 账户状态报告\n\n"
                "✅ 状态：活跃正常\n"
                "--------------------\n"
                f"👤 账号邮箱：`{email}`\n"
                f"🔑 Token掩码：`{masked_token}`\n"
                f"⏰ 北京时间：`{current_time}`\n"
                "--------------------\n"
                "✨ 账户运行良好，无需任何操作。"
            )
        else:
            # --- 失败通知 (无加粗, 北京时间) ---
            summary = (
                "🚨 Koyeb 账户异常警报\n\n"
                "❌ 状态：检测失败\n"
                "--------------------\n"
                f"🔑 Token掩码：`{masked_token}`\n"
                f"🚫 错误原因：{result_msg}\n"
                f"⏰ 北京时间：`{current_time}`\n"
                "--------------------\n"
                "⚠️ 建议操作：\n"
                "请登录 Koyeb 控制台检查，或更新环境变量 Token。"
            )

        send_tg_message(summary)
        send_pushplus_message(summary)
        logging.info("检查完成，通知已推送")

    except Exception as e:
        current_time = get_beijing_time()
        # --- 错误通知 (无加粗, 北京时间) ---
        error_msg = (
            "💣 Koyeb 脚本运行错误\n\n"
            f"❌ 错误信息：`{str(e)}`\n"
            f"⏰ 北京时间：`{current_time}`\n\n"
            "请检查环境变量配置或网络连接。"
        )
        logging.error(error_msg)
        send_tg_message(error_msg)
        send_pushplus_message(error_msg)

if __name__ == "__main__":
    main()
