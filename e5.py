#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Office 365 E5 订阅巡检与日报推送

相对旧版 e5.py 的修复：
  1. [P0] SKU 匹配改白名单直取，不再用子串猜
         旧版 `any(k in raw_sku for k in ["E3", ...])` 漏掉 ENTERPRISEPACK /
         ENTERPRISEPREMIUM / O365_BUSINESS_PREMIUM —— `sku_map` 里的中文名是死代码
  2. [P0] PushPlus 校验业务码 code==200
         旧版 HTTP 200 即打印"✅ 推送成功"，token 失效(code=903)照样报成功
  3. [P0] 失败以非 0 退出码结束，让 Actions 红灯真实反映状态
  4. [P1] 日志与日报统一脱敏；短 ID 整体掩掉（旧版 mask 对短值自曝）
  5. [P2] 429 退避重试 / 异常不再裸吞 / 推送走 HTTPS / 依赖版本收敛
"""

import os
import sys
import time
from datetime import datetime, timezone, timedelta

import requests

GRAPH = "https://graph.microsoft.com/v1.0"
TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
PUSHPLUS_URL = "https://www.pushplus.plus/send"

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "20"))
MAX_RETRY = int(os.getenv("MAX_RETRY", "2"))
MAX_ACCOUNTS = 10

# Graph subscribedSkus 的 skuPartNumber 白名单。
# 只按真实 SKU 名匹配，不做子串猜测 —— 子串法已经证明会漏 E3 全线。
SKU_MAP = {
    "DEVELOPERPACK_E5": "M365 E5 开发者版",
    "DEVELOPERPACK": "M365 开发者版",
    "SPE_E5": "M365 E5",
    "SPE_E3": "M365 E3",
    "ENTERPRISEPACK": "O365 E3 企业版",
    "ENTERPRISEPREMIUM": "O365 E5 企业版",
    "O365_BUSINESS_PREMIUM": "M365 商业高级版",
    "O365_BUSINESS_ESSENTIALS": "M365 商业基础版",
}


# ===================== 工具函数 =====================

def get_beijing_time():
    utc_now = datetime.now(timezone.utc)
    return utc_now.astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")


def mask_id(value):
    """脱敏：GUID 保留首 8 末 4；短值整体掩掉，避免"脱敏"反而自曝完整值。"""
    if not value:
        return "(未配置)"
    value = value.strip()
    if len(value) < 20:
        return "****"
    return "{}-****-****-****-{}".format(value[:8], value[-4:])


def _request(method, url, **kwargs):
    """统一请求入口：超时兜底 + 429 退避重试。"""
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    resp = None
    for attempt in range(MAX_RETRY + 1):
        resp = requests.request(method, url, **kwargs)
        if resp.status_code != 429 or attempt >= MAX_RETRY:
            return resp
        raw = resp.headers.get("Retry-After", "")
        try:
            wait = int(raw)
        except (TypeError, ValueError):
            wait = 5 * (attempt + 1)
        wait = min(max(wait, 1), 30)
        print("  └─ ⏳ 触发限流(429)，{} 秒后重试 ({}/{})".format(wait, attempt + 1, MAX_RETRY))
        time.sleep(wait)
    return resp


# ===================== 账号配置 =====================

def load_accounts():
    """按 TENANT_ID / TENANT_ID_2 / TENANT_ID_3 … 自动发现账号。

    与 README 承诺的 "多账号可追加后缀 _2, _3" 对齐，不再把账号名硬编码在仓库里。
    显示名可用 ACCOUNT_NAME / ACCOUNT_NAME_2 … 覆盖。
    """
    accounts = []
    for i in range(MAX_ACCOUNTS):
        suffix = "" if i == 0 else "_{}".format(i + 1)
        tenant = os.getenv("TENANT_ID" + suffix)
        client_id = os.getenv("CLIENT_ID" + suffix)
        secret = os.getenv("CLIENT_SECRET" + suffix)
        if not (tenant or client_id or secret):
            continue
        accounts.append({
            "index": i + 1,
            "name": os.getenv("ACCOUNT_NAME" + suffix) or "账号{}".format(i + 1),
            "tenant_id": tenant,
            "client_id": client_id,
            "client_secret": secret,
        })
    return accounts


# ===================== Graph 调用 =====================

def get_access_token(acc):
    missing = [k for k in ("tenant_id", "client_id", "client_secret") if not acc.get(k)]
    if missing:
        print("  └─ ❌ 缺少环境变量: {}".format(", ".join(missing).upper()))
        return None

    print("  └─ 🔐 正在请求 Token...")
    url = TOKEN_URL.format(tenant=acc["tenant_id"])
    data = {
        "client_id": acc["client_id"],
        "scope": "https://graph.microsoft.com/.default",
        "client_secret": acc["client_secret"],
        "grant_type": "client_credentials",
    }
    try:
        resp = _request("POST", url, data=data)
    except requests.RequestException as exc:
        print("  └─ ❌ 网络异常: {}: {}".format(type(exc).__name__, exc))
        return None

    if resp.status_code == 200:
        token = (resp.json() or {}).get("access_token")
        if token:
            print("  └─ ✅ Token 获取成功")
            return token
        print("  └─ ❌ 响应中无 access_token")
        return None

    print("  └─ ❌ Token 失败 (HTTP {}): {}".format(resp.status_code, resp.text[:300]))
    return None


def get_extra_info(token):
    headers = {"Authorization": "Bearer " + token}
    # act_state 记录"审计日志到底查没查到"，与"查到了但没有记录"严格区分：
    # 429/超时/权限不足时不能沿用初始值"无记录"，否则失败会被伪装成正常空态。
    info = {"name": "未知组织", "date": "未知", "act": "未知", "act_state": "unknown"}

    print("  └─ 🏢 查询组织信息...")
    try:
        resp = _request("GET", GRAPH + "/organization", headers=headers)
        if resp.status_code == 200:
            values = (resp.json() or {}).get("value") or []
            if values:
                info["name"] = values[0].get("displayName") or info["name"]
                created = (values[0].get("createdDateTime") or "").split("T")[0]
                info["date"] = created or info["date"]
        else:
            print("  └─ ⚠️ 组织信息查询失败 (HTTP {})".format(resp.status_code))
    except (requests.RequestException, ValueError) as exc:
        print("  └─ ⚠️ 组织信息异常: {}: {}".format(type(exc).__name__, exc))

    print("  └─ 📈 查询审计日志...")
    try:
        resp = _request("GET", GRAPH + "/auditLogs/directoryAudits?$top=1", headers=headers)
        if resp.status_code == 200:
            logs = (resp.json() or {}).get("value") or []
            if logs:
                stamp = (logs[0].get("activityDateTime") or "").replace("T", " ").split(".")[0]
                if stamp:
                    info["act"] = stamp + " (UTC)"
                    info["act_state"] = "ok"
                else:
                    info["act"] = "记录缺少时间字段"
                    info["act_state"] = "fail"
            else:
                # 查询成功且确实没有日志 —— 这才是真正的"无记录"
                info["act"] = "无记录（查询成功）"
                info["act_state"] = "ok"
        elif resp.status_code == 403:
            info["act"] = "权限不足（AuditLog.Read.All 未授权）"
            info["act_state"] = "fail"
        elif resp.status_code == 429:
            info["act"] = "查询失败：限流 429（已重试 {} 次）".format(MAX_RETRY)
            info["act_state"] = "fail"
        else:
            info["act"] = "查询失败：HTTP {}".format(resp.status_code)
            info["act_state"] = "fail"
            print("  └─ ⚠️ 审计日志查询失败 (HTTP {})".format(resp.status_code))
    except (requests.RequestException, ValueError) as exc:
        info["act"] = "查询异常：{}".format(type(exc).__name__)
        info["act_state"] = "fail"
        print("  └─ ⚠️ 审计日志异常: {}: {}".format(type(exc).__name__, exc))

    if info["act_state"] == "fail":
        print("  └─ ⚠️ 审计日志不可用：{}".format(info["act"]))

    return info


def get_sub_status(token, acc):
    headers = {"Authorization": "Bearer " + token}
    extra = get_extra_info(token)

    act_icon = {"ok": "", "fail": "⚠️ ", "unknown": "⚠️ "}.get(extra.get("act_state"), "⚠️ ")
    lines = [
        "👤 {} ({})".format(acc["name"], extra["name"]),
        "🆔 应用 ID：",
        mask_id(acc["client_id"]),
        "- 创建日期: {}".format(extra["date"]),
        "- 最近活动: {}{}".format(act_icon, extra["act"]),
    ]

    print("  └─ 📦 查询订阅列表...")
    try:
        resp = _request("GET", GRAPH + "/subscribedSkus", headers=headers)
    except requests.RequestException as exc:
        lines.append("❌ 运行异常: {}: {}".format(type(exc).__name__, exc))
        lines.append("---")
        return "\n".join(lines)

    if resp.status_code != 200:
        lines.append("❌ 订阅查询失败 (HTTP {})".format(resp.status_code))
        lines.append("---")
        return "\n".join(lines)

    try:
        skus = (resp.json() or {}).get("value") or []
    except ValueError:
        lines.append("❌ 订阅响应解析失败")
        lines.append("---")
        return "\n".join(lines)

    matched = 0
    for sub in skus:
        raw = (sub.get("skuPartNumber") or "").upper()
        if raw not in SKU_MAP:
            continue
        matched += 1
        status = sub.get("capabilityStatus") or "Unknown"
        total = (sub.get("prepaidUnits") or {}).get("enabled", 0)
        used = sub.get("consumedUnits", 0)
        icon = "✅" if status == "Enabled" else "⏰"
        lines.append("- {}".format(SKU_MAP[raw]))
        lines.append("  状态: {} {} | 许可: {}/{}".format(icon, status, used, total))

    if matched == 0:
        lines.append("ℹ️ 未发现 E5/E3 订阅（共检查 {} 个 SKU）".format(len(skus)))

    lines.append("---")
    return "\n".join(lines)


# ===================== 推送 =====================

def send_pushplus(content):
    """返回 True 表示推送成功（或未配置因而跳过）。"""
    token = os.getenv("PUSHPLUS_TOKEN")
    if not token:
        print("\n⚠️ 未配置 PUSHPLUS_TOKEN，跳过推送")
        return True

    print("\n📢 发送推送中...")
    payload = {
        "token": token,
        "title": "Office 365 监控日报",
        "content": content,
        "template": "markdown",
    }
    try:
        resp = _request("POST", PUSHPLUS_URL, json=payload)
    except requests.RequestException as exc:
        print("❌ 推送异常: {}: {}".format(type(exc).__name__, exc))
        return False

    try:
        body = resp.json() or {}
    except ValueError:
        print("❌ 推送失败: HTTP {} 非 JSON 响应: {}".format(resp.status_code, resp.text[:200]))
        return False

    # PushPlus 用业务码表达结果，HTTP 200 不代表成功（实测 token 失效返回 code=903）
    if resp.status_code == 200 and body.get("code") == 200:
        print("✅ 推送成功")
        return True

    print("❌ 推送失败: HTTP {} code={} msg={}".format(
        resp.status_code, body.get("code"), body.get("msg")))
    return False


# ===================== 主流程 =====================

def main():
    started = time.time()
    bj_time = get_beijing_time()
    print("🚀 开始执行巡检 | {}\n".format(bj_time))

    accounts = load_accounts()
    if not accounts:
        print("❌ 未发现任何账号配置（需要 TENANT_ID / CLIENT_ID / CLIENT_SECRET）")
        return 1

    report = ["📋 Office 365 监控日报", "📅 时间: {}".format(bj_time), "---"]
    token_failures = 0
    degraded = []  # 审计日志查不到但不影响主指标的情况

    for acc in accounts:
        print("🔍 正在处理: {} (#{})".format(acc["name"], acc["index"]))
        print("  └─ ID: {}".format(mask_id(acc["client_id"])))

        token = get_access_token(acc)
        if token:
            report.append(get_sub_status(token, acc))
            print("✨ {} 完成\n".format(acc["name"]))
        else:
            token_failures += 1
            report.append(
                "👤 {}\n🆔 应用 ID：\n{}\n❌ 获取 Token 失败\n---".format(
                    acc["name"], mask_id(acc["client_id"]))
            )
            print("❌ {} 失败\n".format(acc["name"]))

    report_text = "\n".join(report)
    print("=" * 30)
    print(report_text)
    print("=" * 30)

    pushed = send_pushplus(report_text)
    print("\n⏱️ 耗时 {:.1f}s | 账号 {} 个 | Token 失败 {} 个".format(
        time.time() - started, len(accounts), token_failures))

    if not pushed:
        print("❌ 退出码 1：推送未成功")
        return 1
    if token_failures:
        print("❌ 退出码 1：{} 个账号获取 Token 失败".format(token_failures))
        return 1

    # 审计日志不可用时给出可见告警，但不让整个续期链条红灯
    # —— 续期真正依赖的是 Token 与订阅状态，审计日志只影响"最近活动"的展示。
    degraded_hits = report_text.count("⚠️ 查询") + report_text.count("⚠️ 权限不足")
    if degraded_hits:
        print("⚠️ 退出码 0，但有 {} 处降级：审计日志不可用（见日报中 ⚠️ 标记）".format(degraded_hits))
        return 0

    print("✅ 退出码 0：全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
