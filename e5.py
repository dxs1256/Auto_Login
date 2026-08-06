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
    utc_dt = datetime.now(timezone.utc)
    bj_dt = utc_dt.astimezone(timezone(timedelta(hours=8)))
    return bj_dt.strftime('%Y-%m-%d %H:%M:%S')

def get_access_token(tenant_id, client_id, client_secret):
    """获取 Token 并打印详细日志"""
    if not all([tenant_id, client_id, client_secret]):
        print("  └─ ❌ 错误: 环境变量不完整")
        return None
    
    print(f"  └─ 🔐 正在请求 Token...")
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        'client_id': client_id,
        'scope': 'https://graph.microsoft.com/.default',
        'client_secret': client_secret,
        'grant_type': 'client_credentials'
    }
    try:
        res = requests.post(url, data=data, timeout=20)
        if res.status_code == 200:
            print("  └─ ✅ Token 获取成功")
            return res.json().get('access_token')
        print(f"  └─ ❌ Token 失败: {res.text}")
    except Exception as e:
        print(f"  └─ ❌ 网络异常: {e}")
    return None

def get_extra_info(token):
    """获取组织和审计信息并打印日志"""
    headers = {'Authorization': f'Bearer {token}'}
    info = {"name": "未知组织", "date": "未知", "act": "无记录"}
    try:
        print("  └─ 🏢 查询组织信息...")
        r1 = requests.get("https://graph.microsoft.com/v1.0/organization", headers=headers, timeout=20)
        if r1.status_code == 200:
            d = r1.json()['value'][0]
            info["name"] = d.get('displayName')
            info["date"] = d.get('createdDateTime', '').split('T')[0]

        print("  └─ 📈 查询审计日志...")
        audit_url = "https://graph.microsoft.com/v1.0/auditLogs/directoryAudits?$top=1"
        r2 = requests.get(audit_url, headers=headers, timeout=20)
        if r2.status_code == 200:
            logs = r2.json().get('value', [])
            if logs:
                info["act"] = logs[0].get('activityDateTime', '').replace('T', ' ').split('.')[0] + " (UTC)"
        elif r2.status_code == 403:
            info["act"] = "❌ 权限不足"
    except:
        pass
    return info

def get_sub_status(token, account_name, client_id):
    """查询订阅并格式化消息"""
    headers = {'Authorization': f'Bearer {token}'}
    extra = get_extra_info(token)
    
    # 日报中的 ID 处理
    masked_id = f"{client_id[:8]}-****-****-****-{client_id[-4:]}"

    msg = []
    # 顶部基本信息
    msg.append(f"👤 {account_name} ({extra['name']})")
    msg.append(f"🆔 应用 ID：")
    msg.append(f"{masked_id}") # 另起一行，不带特殊格式
    msg.append(f"- 创建日期: {extra['date']}")
    msg.append(f"- 最近活动: {extra['act']}")
    
    try:
        print("  └─ 📦 查询订阅列表...")
        res = requests.get("https://graph.microsoft.com/v1.0/subscribedSkus", headers=headers, timeout=20)
        if res.status_code == 200:
            sku_map = {"DEVELOPERPACK_E5": "M365 E5 开发者版", "ENTERPRISEPACK": "O365 E3 企业版"}
            for sub in res.json().get('value', []):
                raw_sku = sub.get('skuPartNumber', '').upper()
                if any(k in raw_sku for k in ["E5", "E3", "DEVELOPER", "OFFICE"]):
                    name = sku_map.get(raw_sku, raw_sku)
                    st = sub.get('capabilityStatus')
                    total = sub.get('prepaidUnits', {}).get('enabled', 0)
                    used = sub.get('consumedUnits', 0)
                    icon = "✅" if st == "Enabled" else "⏰"
                    msg.append(f"- {name}")
                    msg.append(f"  状态: {icon} {st} | 许可: {used}/{total}")
        else:
            msg.append(f"❌ 订阅查询失败 ({res.status_code})")
    except Exception as e:
        msg.append(f"❌ 运行异常: {str(e)}")
    
    msg.append("---")
    return "\n".join(msg)

def send_pushplus(content):
    if not PUSHPLUS_TOKEN: return
    print(f"\n📢 发送推送中...")
    data = {"token": PUSHPLUS_TOKEN, "title": "Office 365 监控日报", "content": content, "template": "markdown"}
    try:
        requests.post('http://www.pushplus.plus/send', json=data, timeout=20)
        print("✅ 推送成功")
    except:
        print("❌ 推送失败")

# ================= 主程序 =================
if __name__ == "__main__":
    bj_time = get_beijing_time()
    print(f"🚀 开始执行巡检 | {bj_time}\n")
    
    full_report = [f"📋 Office 365 监控日报", f"📅 时间: {bj_time}", "---"]
    
    for acc in ACCOUNTS:
        name, cid = acc['name'], acc['client_id']
        print(f"🔍 正在处理: {name}")
        print(f"  └─ ID: {cid}")
        
        token = get_access_token(acc['tenant_id'], cid, acc['client_secret'])
        if token:
            full_report.append(get_sub_status(token, name, cid))
            print(f"✨ {name} 完成\n")
        else:
            full_report.append(f"👤 {name}\n🆔 应用 ID：\n{cid}\n❌ 获取 Token 失败\n---")
            print(f"❌ {name} 失败\n")

    report_text = "\n".join(full_report)
    print("="*30 + "\n" + report_text + "\n" + "="*30)
    send_pushplus(report_text)
