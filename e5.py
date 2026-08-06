import requests
import os
import json
from datetime import datetime, timezone, timedelta

# ================= 配置多账号 =================
ACCOUNTS = [
    {
        "name": "situ@mesitu",
        "tenant_id": os.getenv('TENANT_ID'),
        "client_id": os.getenv('CLIENT_ID'),
        "client_secret": os.getenv('CLIENT_SECRET')
    },
    {
        "name": "orrz@x7pt5",
        "tenant_id": os.getenv('TENANT_ID_2'),
        "client_id": os.getenv('CLIENT_ID_2'),
        "client_secret": os.getenv('CLIENT_SECRET_2')
    }
]

PUSHPLUS_TOKEN = os.getenv('PUSHPLUS_TOKEN')

# ================= 辅助函数 =================

def get_beijing_time():
    """获取北京时间字符串"""
    utc_dt = datetime.now(timezone.utc)
    bj_dt = utc_dt.astimezone(timezone(timedelta(hours=8)))
    return bj_dt.strftime('%Y-%m-%d %H:%M:%S')

def get_access_token(tenant_id, client_id, client_secret, account_name):
    """获取 Token"""
    if not all([tenant_id, client_id, client_secret]):
        print(f"  └─ ❌ 错误: 环境变量配置不完整")
        return None
        
    print(f"  └─ 🔐 正在向 Microsoft 申请 Access Token...")
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {
        'client_id': client_id,
        'scope': 'https://graph.microsoft.com/.default',
        'client_secret': client_secret,
        'grant_type': 'client_credentials'
    }

    try:
        response = requests.post(url, headers=headers, data=data, timeout=20)
        if response.status_code == 200:
            print(f"  └─ ✅ Token 获取成功")
            return response.json().get('access_token')
        else:
            print(f"  └─ ❌ Token 获取失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"  └─ ❌ 网络请求异常: {e}")
        return None

def get_extra_info(token, account_name):
    """获取租户名称、创建时间和最近活跃日志"""
    headers = {'Authorization': f'Bearer {token}'}
    info = {"org_name": "未知组织", "created_date": "未知", "activity": "无记录"}
    
    try:
        # 1. 查询租户详细信息
        print(f"  └─ 🏢 正在查询组织详细信息...")
        org_res = requests.get("https://graph.microsoft.com/v1.0/organization", headers=headers, timeout=20)
        if org_res.status_code == 200:
            org_data = org_res.json()['value'][0]
            info["org_name"] = org_data.get('displayName')
            info["created_date"] = org_data.get('createdDateTime', '').split('T')[0]
            print(f"    └─ 组织名: {info['org_name']}")

        # 2. 查询最近审计日志
        print(f"  └─ 📈 正在检测 API 开发活跃度 (AuditLogs)...")
        audit_url = "https://graph.microsoft.com/v1.0/auditLogs/directoryAudits?$top=1"
        audit_res = requests.get(audit_url, headers=headers, timeout=20)
        if audit_res.status_code == 200:
            logs = audit_res.json().get('value', [])
            if logs:
                raw_time = logs[0].get('activityDateTime', '')
                info["activity"] = raw_time.replace('T', ' ').split('.')[0] + " (UTC)"
                print(f"    └─ 最近活动时间: {info['activity']}")
            else:
                info["activity"] = "⚠️ 近期无活跃记录"
                print(f"    └─ ⚠️ 未发现审计记录")
        elif audit_res.status_code == 403:
            info["activity"] = "❌ 缺少 AuditLog 权限"
            print(f"    └─ ❌ 权限不足(403): 请在 Azure 开启 AuditLog.Read.All")
    except Exception as e:
        print(f"    └─ ⚠️ 获取额外信息时发生非致命异常: {e}")
        
    return info

def get_sub_status(token, account_name, client_id):
    """查询并格式化单个账号的状态"""
    headers = {'Authorization': f'Bearer {token}'}
    
    # 步骤：获取额外信息
    extra = get_extra_info(token, account_name)
    
    # 对 Client ID 进行脱敏处理
    masked_id = f"{client_id[:8]}-****-****-****-{client_id[-4:]}" if client_id else "Unknown"

    sku_mapping = {
        "ENTERPRISEPACK": "Office 365 E3 (企业版)",
        "DEVELOPERPACK_E5": "Microsoft 365 E5 开发者版",
        "SPE_E5": "Microsoft 365 E5 (商业版)",
        "SPE_E3": "Microsoft 365 E3 (商业版)",
        "DESKLESSPACK": "Office 365 F3 (一线员工版)"
    }
    status_mapping = {"Enabled": "正常", "Suspended": "已禁用", "Warning": "警告", "Deleted": "已删除"}

    msg_lines = []
    # --- 手机排版优化 ---
    msg_lines.append(f"👤 **账号：{account_name}**")
    msg_lines.append(f"🏢 **组织：{extra['org_name']}**")
    msg_lines.append(f"🆔 **应用 ID：**")
    msg_lines.append(f"`{masked_id}`")  # 独占一行且使用代码块格式
    msg_lines.append(f"📅 租户创建日期: {extra['created_date']}")
    msg_lines.append(f"📈 最近开发活动: {extra['activity']}")
    
    try:
        print(f"  └─ 📦 正在拉取订阅许可证数据...")
        url = "https://graph.microsoft.com/v1.0/subscribedSkus"
        response = requests.get(url, headers=headers, timeout=20)
        
        if response.status_code != 200:
            print(f"    └─ ❌ 订阅查询失败: {response.status_code}")
            return f"❌ {account_name}: API 订阅查询失败 ({response.status_code})"

        data = response.json()
        found_target = False 

        for sub in data.get('value', []):
            raw_sku = sub.get('skuPartNumber', 'Unknown').upper()
            target_keywords = ["DEVELOPER", "E5", "ENTERPRISE", "PREMIUM", "OFFICE"]
            
            if any(k in raw_sku for k in target_keywords) and raw_sku not in ["FLOW_FREE", "TEAMS_EXPLORATORY"]:
                found_target = True
                raw_status = sub.get('capabilityStatus')
                enabled_count = sub.get('prepaidUnits', {}).get('enabled', 0)
                consumed_count = sub.get('consumedUnits', 0)

                cn_name = sku_mapping.get(raw_sku, raw_sku)
                cn_status = status_mapping.get(raw_status, raw_status)
                icon = "✅" if raw_status == "Enabled" else "⏰"

                msg_lines.append(f"订阅: {cn_name}")
                msg_lines.append(f"  - 状态: {icon} {cn_status}")
                msg_lines.append(f"  - 许可: {consumed_count} / {enabled_count} (已用/总数)")
                print(f"    └─ 发现订阅: {cn_name} [{cn_status}]")
        
        if not found_target:
            msg_lines.append(f"⚠️ 未检测到有效的主订阅")
            print(f"    └─ ⚠️ 未发现 E3/E5 等目标订阅")

    except Exception as e:
        msg_lines.append(f"❌ 查询异常: {str(e)}")
        print(f"    └─ ❌ 查询过程崩溃: {e}")
    
    msg_lines.append("---")
    return "\n".join(msg_lines)

def send_pushplus(content):
    if not PUSHPLUS_TOKEN:
        print("⚠️ 未配置 PUSHPLUS_TOKEN，跳过推送")
        return
    
    print(f"\n📢 正在准备发送 PushPlus 推送...")
    url = 'http://www.pushplus.plus/send'
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": "Office 365 监控日报",
        "content": content,
        "template": "markdown"
    }
    try:
        res = requests.post(url, json=data, timeout=20)
        if res.status_code == 200:
            print("✅ PushPlus 推送成功")
        else:
            print(f"❌ PushPlus 接口返回错误: {res.text}")
    except Exception as e:
        print(f"❌ 推送失败: {e}")

# ================= 主程序 =================
if __name__ == "__main__":
    bj_now = get_beijing_time()
    print(f"{'='*30}")
    print(f"🚀 M365 多账号监控启动")
    print(f"⏰ 北京时间: {bj_now}")
    print(f"{'='*30}\n")
    
    full_report = []
    full_report.append("📋 **Office 365 监控日报**")
    full_report.append(f"📅 时间: {bj_now}")
    full_report.append("---")
    
    for acc in ACCOUNTS:
        name = acc['name']
        cid = acc['client_id']
        
        print(f"🔍 正在处理账号: {name}")
        print(f"  └─ 🆔 Client ID: {cid}")
        
        if not acc['tenant_id']:
            print(f"  └─ ⚠️ 跳过: 缺少租户 ID 配置")
            continue
            
        token = get_access_token(acc['tenant_id'], cid, acc['client_secret'], name)
        
        if token:
            sub_info = get_sub_status(token, name, cid)
            full_report.append(sub_info)
            print(f"✨ {name} 处理完成\n")
        else:
            # 失败情况下的排版
            err_msg = [
                f"👤 **账号：{name}**",
                f"🆔 **应用 ID：**",
                f"`{cid}`",
                f"❌ **状态：获取 Token 失败**",
                "请检查 Azure 端的客户端密码(Secret)是否过期。",
                "---"
            ]
            full_report.append("\n".join(err_msg))
            print(f"❌ {name} 处理失败\n")

    # 合并报告
    final_content = "\n".join(full_report)
    
    # 打印最终报告预览到 GitHub 日志
    print(f"{'='*30}")
    print("总报告预览：")
    print(final_content)
    print(f"{'='*30}")
    
    # 推送
    send_pushplus(final_content)
