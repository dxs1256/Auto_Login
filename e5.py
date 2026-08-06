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

def get_access_token(tenant_id, client_id, client_secret):
    """获取 Token"""
    if not all([tenant_id, client_id, client_secret]):
        return None
        
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {
        'client_id': client_id,
        'scope': 'https://graph.microsoft.com/.default',
        'client_secret': client_secret,
        'grant_type': 'client_credentials'
    }

    try:
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            return response.json().get('access_token')
        else:
            print(f"Token 获取失败: {response.text}")
            return None
    except Exception as e:
        print(f"网络请求异常: {e}")
        return None

def get_extra_info(token):
    """获取租户名称、创建时间和最近活跃日志"""
    headers = {'Authorization': f'Bearer {token}'}
    info = {"org_name": "未知组织", "created_date": "未知", "activity": "无记录"}
    
    try:
        # 1. 查询租户详细信息
        org_res = requests.get("https://graph.microsoft.com/v1.0/organization", headers=headers)
        if org_res.status_code == 200:
            org_data = org_res.json()['value'][0]
            info["org_name"] = org_data.get('displayName')
            info["created_date"] = org_data.get('createdDateTime', '').split('T')[0]

        # 2. 查询最近审计日志
        audit_url = "https://graph.microsoft.com/v1.0/auditLogs/directoryAudits?$top=1"
        audit_res = requests.get(audit_url, headers=headers)
        if audit_res.status_code == 200:
            logs = audit_res.json().get('value', [])
            if logs:
                raw_time = logs[0].get('activityDateTime', '')
                info["activity"] = raw_time.replace('T', ' ').split('.')[0] + " (UTC)"
            else:
                info["activity"] = "⚠️ 近期无活跃记录"
    except:
        pass
    return info

def get_sub_status(token, account_name, client_id):
    """查询单个账号的状态"""
    headers = {'Authorization': f'Bearer {token}'}
    extra = get_extra_info(token)
    
    # 对 Client ID 进行脱敏处理用于日报展示 (例如: 12345678-****-****-****-abcd)
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
    msg_lines.append(f"👤 {account_name} ({extra['org_name']})") 
    msg_lines.append(f"🆔 应用ID: {masked_id}") # 日报中增加 ID 展示
    msg_lines.append(f"- 租户创建日期: {extra['created_date']}")
    msg_lines.append(f"- 最近开发活动: {extra['activity']}")
    
    try:
        url = "https://graph.microsoft.com/v1.0/subscribedSkus"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return f"❌ {account_name}: API 请求失败 ({response.status_code})"

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

                msg_lines.append(f"- {cn_name}")
                msg_lines.append(f"  - 状态: {icon} {cn_status}")
                msg_lines.append(f"  - 许可: {consumed_count}已分配 / {enabled_count}总量")
        
        if not found_target:
            msg_lines.append(f"⚠️ {account_name}: 未检测到主订阅")

    except Exception as e:
        msg_lines.append(f"❌ {account_name}: 查询异常 {str(e)}")
    
    msg_lines.append("---")
    return "\n".join(msg_lines)

def send_pushplus(content):
    if not PUSHPLUS_TOKEN: return
    url = 'http://www.pushplus.plus/send'
    data = {"token": PUSHPLUS_TOKEN, "title": "Office 365 监控日报", "content": content, "template": "markdown"}
    try:
        requests.post(url, json=data)
        print("✅ PushPlus 推送成功")
    except Exception as e:
        print(f"❌ 推送失败: {e}")

# ================= 主程序 =================
if __name__ == "__main__":
    print(f"🚀 开始执行多账号监控... {get_beijing_time()}")
    
    full_report = []
    full_report.append("📋 Office 365 监控日报")
    full_report.append(f"📅 北京时间: {get_beijing_time()}")
    full_report.append("---")
    
    for acc in ACCOUNTS:
        curr_client_id = acc['client_id']
        if not acc['tenant_id']:
            continue
            
        # 控制台打印：显示完整 Client ID 方便你排查
        print(f"正在查询: {acc['name']}")
        print(f"🔗 对应 Client ID: {curr_client_id}")
        
        token = get_access_token(acc['tenant_id'], curr_client_id, acc['client_secret'])
        
        if token:
            sub_info = get_sub_status(token, acc['name'], curr_client_id)
            full_report.append(sub_info)
            print(f"✅ {acc['name']} 查询成功")
        else:
            full_report.append(f"👤 {acc['name']}")
            full_report.append(f"🆔 应用ID: {curr_client_id}")
            full_report.append("❌ 获取 Token 失败，请检查 Secret 配置")
            full_report.append("---")
            print(f"❌ {acc['name']} 查询失败")

    final_content = "\n".join(full_report)
    send_pushplus(final_content)
