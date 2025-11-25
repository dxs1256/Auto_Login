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

def get_sub_status(token, account_name):
    """查询单个账号的状态"""
    url = "https://graph.microsoft.com/v1.0/subscribedSkus"
    headers = {'Authorization': f'Bearer {token}'}
    
    # 汉化与映射配置
    sku_mapping = {
        "ENTERPRISEPACK": "Office 365 E3 (企业版)",
        "DEVELOPERPACK_E5": "Microsoft 365 E5 开发者版",
        "SPE_E5": "Microsoft 365 E5 (商业版)",
        "SPE_E3": "Microsoft 365 E3 (商业版)",
        "DESKLESSPACK": "Office 365 F3 (一线员工版)",
        "FLOW_FREE": "Power Automate (免费版)",
        "TEAMS_EXPLORATORY": "Teams 探索版"
    }
    
    status_mapping = {
        "Enabled": "正常",
        "Suspended": "已禁用",
        "Warning": "警告 (即将过期)",
        "Deleted": "已删除",
        "LockedOut": "已被锁定"
    }

    msg_lines = []
    # 账号名称 (加粗)
    msg_lines.append(f"**👤 {account_name}**") 
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return f"❌ {account_name}: API 请求失败 ({response.status_code})"

        data = response.json()
        found_target = False 

        for sub in data.get('value', []):
            raw_sku = sub.get('skuPartNumber', 'Unknown').upper()
            
            # 筛选配置
            ignore_list = ["FLOW_FREE", "TEAMS_EXPLORATORY", "POWER_BI_STANDARD"]
            target_keywords = ["DEVELOPER", "E5", "ENTERPRISE", "PREMIUM", "OFFICE"]
            
            is_target = any(k in raw_sku for k in target_keywords)
            
            if is_target and raw_sku not in ignore_list:
                found_target = True
                
                raw_status = sub.get('capabilityStatus')
                prepaid = sub.get('prepaidUnits', {})
                enabled_count = prepaid.get('enabled', 0)
                warning_count = prepaid.get('warning', 0)

                # 汉化
                cn_name = sku_mapping.get(raw_sku, raw_sku)
                cn_status = status_mapping.get(raw_status, raw_status)

                # 图标
                icon = "✅" 
                if raw_status == "Warning": icon = "⏰"
                if raw_status == "Suspended": icon = "❌"

                msg_lines.append(f"- {cn_name}")
                msg_lines.append(f"  - 状态: {icon} {cn_status}")
                msg_lines.append(f"  - 许可: {enabled_count}")
                
                if warning_count > 0:
                    msg_lines.append(f"  - ⚠️ 警告: {warning_count}")
        
        if not found_target:
            msg_lines.append(f"⚠️ {account_name}: 未检测到 E5/E3 主订阅")

    except Exception as e:
        msg_lines.append(f"❌ {account_name}: 查询异常 {str(e)}")
    
    msg_lines.append("---") # 分割线
    return "\n".join(msg_lines)

def send_pushplus(content):
    if not PUSHPLUS_TOKEN: return
    
    url = 'http://www.pushplus.plus/send'
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": "Office 365 监控日报",
        "content": content,
        "template": "markdown"
    }
    try:
        requests.post(url, json=data)
        print("✅ PushPlus 推送成功")
    except Exception as e:
        print(f"❌ 推送失败: {e}")

# ================= 主程序 =================
if __name__ == "__main__":
    print("🚀 开始执行多账号监控...")
    
    full_report = []
    # 标题加粗，使用北京时间
    full_report.append(f"**📋 Office 365 监控日报**")
    full_report.append(f"📅 北京时间: {get_beijing_time()}\n")
    
    for acc in ACCOUNTS:
        if not acc['tenant_id']:
            print(f"⚠️ 跳过 {acc['name']}：未配置环境变量")
            continue
            
        print(f"正在查询: {acc['name']} ...")
        token = get_access_token(acc['tenant_id'], acc['client_id'], acc['client_secret'])
        
        if token:
            sub_info = get_sub_status(token, acc['name'])
            full_report.append(sub_info)
        else:
            full_report.append(f"**👤 {acc['name']}**\n❌ 获取 Token 失败，请检查 Secret 配置\n---")

    # 合并发送
    final_content = "\n".join(full_report)
    print(final_content)
    send_pushplus(final_content)
