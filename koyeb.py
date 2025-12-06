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
    koyeb_tokens_env = os.getenv("KOYEB_TOKENS")
    if not koyeb_tokens_env:
        raise ValueError("❌ KOYEB_TOKENS 环境变量未设置")
    try:
        return json.loads(koyeb_tokens_env)
    except json.JSONDecodeError:
        # 兼容只设置了一个 token 的情况（非JSON格式）
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
        "title": "Koyeb 活跃检查通知",
        "content": message,
        "template": "markdown",
        "channel": "wechat"
    }

    try:
        requests.post(url, json=data, timeout=10)
    except Exception as e:
        logging.error(f"PushPlus 发送失败: {e}")

def check_koyeb_activity(token):
    """
    使用 API Token 获取用户信息或服务列表
    这会被视为一次有效的 API 交互，通常足以证明账户活跃
    """
    # 获取用户信息的 API 端点
    url = "https://app.koyeb.com/v1/account/profile"
    # 或者列出 App 的端点: "https://app.koyeb.com/v1/apps"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            # 尝试获取用户名或邮箱来证明成功
            email = data.get("user", {}).get("email", "Unknown")
            return True, f"API 调用成功 (账户: {email})"
        elif response.status_code == 401:
            return False, "Token 无效或已过期"
        else:
            return False, f"API 错误: {response.status_code} - {response.text[:50]}"
            
    except requests.Timeout:
        return False, "请求超时"
    except requests.RequestException as e:
        return False, str(e)

def main():
    """主流程"""
    try:
        tokens = validate_env_variables()
        if not tokens:
            raise ValueError("❌ 未找到 Token")

        # 获取北京时间
        current_time = (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
        messages = []
        success_count = 0

        for index, token in enumerate(tokens):
            masked_token = token[:5] + "***" + token[-5:] if len(token) > 10 else "Invalid"
            logging.info(f"🔄 正在检查 Token {index + 1}: {masked_token}")
            
            success, message = check_koyeb_activity(token)
            
            status_icon = "✅" if success else "❌"
            messages.append(f"{status_icon} **Token {index + 1}**: {message}")
            
            if success:
                success_count += 1
            
            # 避免请求过快
            time.sleep(2)

        # 汇总消息
        summary = f"🗓️ **Koyeb 活跃检查**\n时间: {current_time}\n\n" + "\n".join(messages)
        summary += f"\n\n📊 成功: {success_count}/{len(tokens)}"

        logging.info("📋 任务完成，发送通知")
        send_tg_message(summary)
        send_pushplus_message(summary)

    except Exception as e:
        logging.error(f"执行出错: {e}")
        send_tg_message(f"❌ Koyeb 脚本执行出错: {e}")

if __name__ == "__main__":
    main()
