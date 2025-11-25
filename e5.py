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
    
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
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
    """查询订阅状态并返回汉化后的消息"""
    url = "https://graph.microsoft.com/v1.0/subscribedSkus"
    headers = {
        'Authorization': f'Bearer {token}'
    }
    
    msg_lines = []
    
    # ================= 汉化字典 =================
    # 订阅名称映射表
    sku_mapping = {
        "ENTERPRISEPACK": "Office 365 E3 (企业版)",
        "DEVELOPERPACK_E5": "Microsoft 365 E5 开发者版",
        "SPE_E5": "Microsoft 365 E5 (商业版)",
        "SPE_E3": "Microsoft 365 E3 (商业版)",
        "DESKLESSPACK": "Office 365 F3 (一线员工版)",
        "FLOW_FREE": "Power Automate (免费版)",
        "TEAMS_EXPLORATORY": "Teams 探索版"
    }

    # 状态映射表
    status_mapping = {
        "Enabled": "正常",
        "Suspended": "已禁用",
        "Warning": "警告 (即将过期)",
        "Deleted": "已删除",
        "LockedOut": "已被锁定"
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return f"❌ API 请求失败: {response.status_code}\n{response.text}"

        data = response.json()
        found_target = False 

        msg_lines.append("## 📋 Office 365 订阅监控")
        msg_lines.append(f"📅 查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        msg_lines.append("---")

        for sub in data.get('value', []):
            raw_sku = sub.get('skuPartNumber', 'Unknown').upper()
            
            # 筛选逻辑：忽略一些不重要的免费订阅
            ignore_list = ["FLOW_FREE", "TEAMS_EXPLORATORY", "POWER_BI_STANDARD"]
            
            # 关键词匹配
            target_keywords = ["DEVELOPER", "E5", "ENTERPRISE", "PREMIUM", "OFFICE"]
            
            # 判断是否是我们需要监控的目标
            is_target = any(k in raw_sku for k in target_keywords)
            
            if is_target and raw_sku not in ignore_list:
                found_target = True
                
                raw_status = sub.get('capabilityStatus')
                prepaid = sub.get('prepaidUnits', {})
                enabled_count = prepaid.get('enabled', 0)
                suspended_count = prepaid.get('suspended', 0)
                warning_count = prepaid.get('warning', 0)

                # --- 开始翻译 ---
                # 1. 翻译产品名称 (如果没有在字典里，就保持英文原名)
                cn_name = sku_mapping.get(raw_sku, raw_sku)
                
                # 2. 翻译状态
                cn_status = status_mapping.get(raw_status, raw_status)

                # 3. 设置图标
                icon = "✅" 
                if raw_status == "Warning": icon = "⏰"
                if raw_status == "Suspended": icon = "❌"
                if raw_status == "Deleted": icon = "🗑️"

                msg_lines.append(f"**📦 订阅名称**: {cn_name}")
                msg_lines.append(f"**📊 当前状态**: {icon} {cn_status}")
                msg_lines.append(f"**👤 许可数量**: {enabled_count}")
                
                if warning_count > 0:
                    msg_lines.append(f"**⏰ 过期警告**: {warning_count} 个许可即将过期")
                if suspended_count > 0:
                    msg_lines.append(f"**❌ 已禁用**: {suspended_count}")
                
                msg_lines.append("---")
        
        if not found_target:
            msg_lines.append("⚠️ 未检测到 E5/E3 主订阅，检测到的所有项目如下：")
            for sub in data.get('value', []):
                name = sub.get('skuPartNumber')
                msg_lines.append(f"- {name} ({sku_mapping.get(name, '未知类型')})")

        return "\n".join(msg_lines)

    except Exception as e:
        return f"❌ 查询过程发生异常: {str(e)}"

def send_pushplus(content):
    """发送结果到 PushPlus"""
    if not PUSHPLUS_TOKEN:
        print("未设置 PUSHPLUS_TOKEN，跳过发送。")
        return

    url = 'http://www.pushplus.plus/send'
    title = "Office 365 订阅状态日报"
    
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": content,
        "template": "markdown"
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
    print("🚀 开始执行 E5/E3 监控脚本...")
    
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
        err_msg = "❌ 监控脚本无法获取 Access Token，请检查 Azure Client Secret 是否过期。"
        print(err_msg)
        send_pushplus(err_msg)
