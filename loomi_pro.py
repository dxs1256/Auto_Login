import requests
import os
import json
import logging
import re
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def get_loomi_credits():
    """获取 https://v2.loomi.live/zh/profile#user 积分数据"""
    email = os.getenv("LOOMI_EMAIL", "unknown")
    run_id = os.getenv("GITHUB_RUN_ID", "local")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://loomi.live",
        "Referer": "https://v2.loomi.live/zh/profile",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site"
    }
    
    try:
        # 🎯 积分概览核心API（对应页面数据）
        url = "https://api.loomi.chat/api/v1/payment/subscription/status"
        resp = requests.get(url, headers=headers, timeout=15)
        
        logger.info(f"积分API状态: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            
            # 解析积分数据（匹配页面结构）
            available_credits = data.get('data', {}).get('available', 0) or data.get('credits', {}).get('available', 0) or 0
            total_credits = data.get('data', {}).get('credits', {}).get('total', 0) or data.get('credits', {}).get('total', 0) or 0
            
            # 格式化输出（匹配页面）
            result = f"""
🎯 积分概览 (https://v2.loomi.live/zh/profile#user)
━━━━━━━━━━━━━━━━━━━━━━
💰 可用积分: {available_credits:,}
💎 总积分:   {total_credits:,}

📅 获取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📧 账号:     {email}
🔢 运行ID:   {run_id}
━━━━━━━━━━━━━━━━━━━━━━
            """
            
            print(result)
            logger.info(f"可用积分: {available_credits}, 总积分: {total_credits}")
            
            # 保存到文件
            with open("credits_report.txt", "w", encoding="utf-8") as f:
                f.write(result)
            
            return {
                "available": available_credits,
                "total": total_credits,
                "success": True
            }
        else:
            logger.error(f"API失败: {resp.status_code} - {resp.text[:200]}")
            return {"success": False}
            
    except Exception as e:
        logger.error(f"异常: {str(e)}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    if os.getenv('GITHUB_ACTIONS'):
        result = get_loomi_credits()
        exit(0 if result.get('success') else 1)
    else:
        get_loomi_credits()
