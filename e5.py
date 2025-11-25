import requests
import os
import json
from datetime import datetime

# ================= 从环境变量获取配置 =================
TENANT_ID = os.getenv('TENANT_ID')
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
PUSHPLUS_TOKEN = os.getenv('PUSHPLUS_TOKEN')

def get_access_token():
    """获取微软 Graph API 的访问令牌"""
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {
        'client_id': CLIENT_ID,
        'scope': 'https://graph.microsoft.com/.default',
        'client_secret': CLIENT_SECRET,
        'grant_type': 'client_credentials'
    }

    try:
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json().get('access_token')
    except Exception as e:
        print(f"❌ 获取 Token 失败: {e}")
        return None

def get_sub_status(token):
    """查询订阅状态并返回格式化消息"""
    url = "https://graph.microsoft.com/v1.0/subscribedSkus"
    headers = {'Authorization': f'Bearer {token}'}
    
    msg_lines = []
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return f"❌ API 请求失败: {response.status_code}\n{response.text}"

        data = response.json()
        found_e5 = False

        msg_lines.append("## 📋 Office 365 E5 订阅监控")
        msg_lines.append(f"📅 查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        msg_lines.append("---")

        for sub in data.get('value', []):
            # 筛选 E5 开发者订阅，通常包含 'DEVELOPERPACK' 或 'E5'
            # 如果你不确定 SKU 名字，脚本会列出所有订阅
            sku_part_number = sub.get('skuPartNumber', 'Unknown')
            
            if "DEVELOPER" in sku_part_number or "E5" in sku_part_number:
                found_e5 = True
                status = sub.get('capabilityStatus')
                prepaid = sub.get('prepaidUnits', {})
                enabled_count = prepaid.get('enabled', 0)
                suspended_count = prepaid.get('suspended', 0)
                warning_count = prepaid.get('warning', 0)

                # 状态判断图标
                icon = "✅" if status == "Enabled" else "⚠️"
                if status == "Suspended": icon = "❌"
                if status == "Warning": icon = "⏰"

                msg_lines.append(f"**产品名称**: {sku_part_number}")
                msg_lines.append(f"**当前状态**: {icon} {status}")
                msg_lines.append(f"**有效数量**: {enabled_count}")
                
                if warning_count > 0:
                    msg_lines.append(f"**⚠️ 警告数量**: {warning_count} (可能即将过期)")
                if suspended_count > 0:
                    msg_lines.append(f"**❌ 禁用数量**: {suspended_count}")
                
                msg_lines.append("---")
        
        if not found_e5:
            msg_lines.append("⚠️ 未在租户中找到显式的 E5 开发者订阅 (SKU name unmatched)。")
            msg_lines.append("已列出所有发现的订阅：")
            for sub in data.get('value', []):
                msg_lines.append(f"- {sub.get('skuPartNumber')}")

        return "\n".join(msg_lines)

    except Exception as e:
        return f"❌ 查询过程发生异常: {str(e)}"

def send_pushplus(content):
    """发送结果到 PushPlus"""
    if not PUSHPLUS_TOKEN:
        print("未设置 PUSHPLUS_TOKEN，跳过发送。")
        return

    url = 'http://www.pushplus.plus/send'
    title = "E5 订阅状态日报"
    
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": content,
        "template": "markdown" # 使用 markdown 格式让排版更好看
    }

    try:
        response = requests.post(url, json=data)
        result = response.json()
        if result.get('code') == 200:
            print("✅ PushPlus 推送成功")
        else:
            print(f"❌ PushPlus 推送失败: {result.get('msg')}")
    except Exception as e:
        print(f"❌ 推送网络异常: {e}")

if __name__ == "__main__":
    print("🚀 开始执行 E5 监控脚本...")
    
    if not all([TENANT_ID, CLIENT_ID, CLIENT_SECRET]):
        print("❌ 错误：环境变量缺失，请检查 Github Secrets 配置。")
        exit(1)

    token = get_access_token()
    if token:
        print("✅ Token 获取成功")
        report = get_sub_status(token)
        print("📋 生成报告内容：")
        print(report)
        send_pushplus(report)
    else:
        send_pushplus("❌ E5 监控脚本无法获取 Access Token，请检查 Azure 应用机密是否过期。")
