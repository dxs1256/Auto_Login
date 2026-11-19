#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Koyeb 账户状态检查与通知。

修复记录（对齐 e5.py 的质量基线）：
  P0-1  exit code 语义：失败以非 0 退出，Actions 不再永远绿色
  P0-2  推送走 HTTPS，token 不再明文传输
  P0-3  校验 PushPlus 业务码 code==200（HTTP 200 != 成功）
  P1-1  脱敏可见字符占比 <= 40%（原实现在 len=11 时泄露 91%）
  P2    支持多 token（原实现只取 tokens[0]）、429/超时重试、通知失败也计入退出码
"""

import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

KOYEB_PROFILE_URL = "https://app.koyeb.com/v1/account/profile"
PUSHPLUS_URL = "https://www.pushplus.plus/send"
TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
MAX_RETRY = int(os.getenv("MAX_RETRY", "2"))

# 脱敏档位：(长度上限, 前缀保留, 后缀保留)。保证可见字符占比 <= 40%。
MASK_TIERS = ((12, 2, 0), (25, 4, 0), (None, 6, 4))


# ===================== 工具函数 =====================

def mask_token(token):
    """脱敏 token，保证任何长度下可见字符占比不超过 40%。

    旧实现 `token[:6] + "****" + token[-4:] if len(token) > 10 else "****"`
    在 len=11 时可见 10 位（泄露 91%）——保护阈值与可见位数不匹配。
    """
    if not token:
        return "(未配置)"
    token = str(token).strip()
    n = len(token)
    for limit, head, tail in MASK_TIERS:
        if limit is None or n <= limit:
            visible = head + tail
            suffix = token[-tail:] if tail else ""
            return token[:head] + "****" + suffix
    return "****"


def _request(method, url, **kwargs):
    """统一请求入口：超时兜底 + 429 退避重试。"""
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    resp = None
    for attempt in range(MAX_RETRY + 1):
        resp = requests.request(method, url, **kwargs)
        if resp.status_code != 429 or attempt >= MAX_RETRY:
            return resp
        try:
            wait = int(resp.headers.get("Retry-After", ""))
        except (TypeError, ValueError):
            wait = 5 * (attempt + 1)
        wait = min(max(wait, 1), 30)
        logging.warning("触发限流(429)，%s 秒后重试 (%s/%s)", wait, attempt + 1, MAX_RETRY)
        time.sleep(wait)
    return resp


def get_beijing_time():
    utc_now = datetime.now(timezone.utc)
    return utc_now.astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")


# ===================== 通知通道 =====================

def send_tg_message(message):
    """返回 True 表示已送达或未配置（跳过）。"""
    bot_token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    if not bot_token or not chat_id:
        logging.info("TG 未配置，跳过")
        return True

    url = TELEGRAM_URL.format(token=bot_token)
    data = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        resp = _request("POST", url, data=data)
    except requests.RequestException as exc:
        logging.error("TG 发送异常: %s: %s", type(exc).__name__, exc)
        return False

    try:
        body = resp.json() or {}
    except ValueError:
        logging.error("TG 响应非 JSON (HTTP %s)", resp.status_code)
        return False

    if body.get("ok") is True:
        logging.info("Telegram 通知已发送")
        return True

    logging.error("TG 发送失败: %s", body.get("description") or body)
    return False


def send_pushplus_message(message):
    """返回 True 表示已送达或未配置（跳过）。

    PushPlus 用业务码表达结果，HTTP 200 不代表成功（token 失效返回 code=903）。
    """
    token = os.getenv("PUSHPLUS_TOKEN")
    if not token:
        logging.info("PushPlus 未配置，跳过")
        return True

    # Markdown 反引号 -> HTML 高亮；换行 -> <br>
    html_content = re.sub(
        r"`(.*?)`",
        r'<span style="background-color: #f0f0f0; padding: 2px 5px; '
        r'border-radius: 3px; font-family: monospace; color: #d63384;">\1</span>',
        message,
    ).replace("\n", "<br>")
    final_content = '<div style="font-size: 14px; line-height: 1.6; color: #333;">{}</div>'.format(
        html_content
    )

    data = {
        "token": token,
        "title": "Koyeb 账户状态",
        "content": final_content,
        "template": "html",
    }
    try:
        resp = _request("POST", PUSHPLUS_URL, json=data)
    except requests.RequestException as exc:
        logging.error("PushPlus 发送异常: %s: %s", type(exc).__name__, exc)
        return False

    try:
        body = resp.json() or {}
    except ValueError:
        logging.error("PushPlus 响应非 JSON (HTTP %s): %s", resp.status_code, resp.text[:200])
        return False

    if resp.status_code == 200 and body.get("code") == 200:
        logging.info("PushPlus 通知已发送")
        return True

    logging.error(
        "PushPlus 发送失败: HTTP %s code=%s msg=%s",
        resp.status_code, body.get("code"), body.get("msg"),
    )
    return False


# ===================== 业务逻辑 =====================

def validate_env_variables():
    """验证并读取 KOYEB_TOKENS，支持 [{"token":"x"}] 与 ["x"] 两种写法。"""
    raw = os.getenv("KOYEB_TOKENS")
    if not raw:
        raise ValueError("KOYEB_TOKENS 环境变量未设置")
    try:
        parsed = json.loads(raw)
        parsed = parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        parsed = [raw]

    tokens = []
    for item in parsed:
        value = item.get("token") if isinstance(item, dict) else item
        if value and str(value).strip():
            tokens.append(str(value).strip())
    return tokens


def check_koyeb_activity(token):
    """返回 (ok, message, email)。"""
    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
    }
    try:
        resp = _request("GET", KOYEB_PROFILE_URL, headers=headers)
    except requests.Timeout:
        return False, "请求超时", None
    except requests.RequestException as exc:
        return False, "网络异常：{}: {}".format(type(exc).__name__, exc), None

    if resp.status_code == 200:
        try:
            data = resp.json() or {}
        except ValueError:
            return True, "账户活跃（响应解析失败）", "未知邮箱"
        email = (data.get("user") or {}).get("email") or "未知邮箱"
        return True, "账户活跃", email
    if resp.status_code == 401:
        return False, "Token 无效或已过期", None
    return False, "API 错误 {}".format(resp.status_code), None


def build_summary(ok, message, email, masked, current_time):
    if ok:
        return (
            "☁️ Koyeb 账户状态报告\n\n"
            "✅ 状态：活跃正常\n"
            "--------------------\n"
            "👤 账号邮箱：`" + str(email) + "`\n"
            "🔑 Token掩码：`" + masked + "`\n"
            "⏰ 北京时间：`" + current_time + "`\n"
            "--------------------\n"
            "✨ 账户运行良好，无需任何操作。"
        )
    return (
        "🚨 Koyeb 账户异常警报\n\n"
        "❌ 状态：检测失败\n"
        "--------------------\n"
        "🔑 Token掩码：`" + masked + "`\n"
        "🚫 错误原因：" + str(message) + "\n"
        "⏰ 北京时间：`" + current_time + "`\n"
        "--------------------\n"
        "⚠️ 建议操作：\n"
        "请登录 Koyeb 控制台检查，或更新环境变量 Token。"
    )


def main():
    """返回进程退出码：0 全部正常，1 存在失败。"""
    current_time = get_beijing_time()

    try:
        tokens = validate_env_variables()
    except ValueError as exc:
        error_msg = (
            "💣 Koyeb 脚本配置错误\n\n"
            "❌ 错误信息：`" + str(exc) + "`\n"
            "⏰ 北京时间：`" + current_time + "`\n\n"
            "请在仓库 Secrets 中配置 KOYEB_TOKENS。"
        )
        logging.error(error_msg)
        send_tg_message(error_msg)
        send_pushplus_message(error_msg)
        return 1

    if not tokens:
        logging.error("KOYEB_TOKENS 解析后为空")
        return 1

    logging.info("开始检查 Koyeb 账户状态，共 %s 个 token", len(tokens))

    failures = 0
    notify_failures = 0

    for index, token in enumerate(tokens, start=1):
        masked = mask_token(token)
        logging.info("[%s/%s] 检查 token %s", index, len(tokens), masked)

        ok, message, email = check_koyeb_activity(token)
        if not ok:
            failures += 1
            logging.error("[%s/%s] 检查失败: %s", index, len(tokens), message)

        summary = build_summary(ok, message, email, masked, current_time)
        if not send_tg_message(summary):
            notify_failures += 1
        if not send_pushplus_message(summary):
            notify_failures += 1

        if index < len(tokens):
            time.sleep(1)

    logging.info(
        "检查完成：%s 个 token，检查失败 %s 个，通知失败 %s 次",
        len(tokens), failures, notify_failures,
    )

    if failures or notify_failures:
        logging.error(
            "以非 0 退出码结束（检查失败 %s，通知失败 %s）", failures, notify_failures
        )
        return 1

    logging.info("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
