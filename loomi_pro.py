import requests
import os
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def get_loomi_credits():
    """安全解析积分数据"""
    email = os.getenv("LOOMI_EMAIL", "unknown")
    run_id = os.getenv("GITHUB_RUN_ID", "local")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://loomi.live",
        "Referer": "https://v2.loomi.live/zh/profile",
    }
    
    try:
        url = "https://api.loomi.chat/api/v1/payment/subscription/status"
        resp = requests.get(url, headers=headers, timeout=15)
        logger.info(f"积分API状态: {resp.status_code}")
        
        if resp.status_code == 200:
            # ✅ 安全解析JSON
            try:
                data = resp.json()
                logger.info(f"完整响应: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}...")
            except json.JSONDecodeError:
                logger.error("JSON解析失败")
                data = {}
            
            # ✅ 多层安全解析（匹配你的HAR数据结构）
            available = 0
            total = 0
            
            # 方案1：data.success.data.credits.available
            if data.get('success') and data.get('data'):
                credits = data['data'].get('credits', {})
                available = credits.get('available', 0)
                total = credits.get('total', 0)
            
            # 方案2：直接从data提取（你的HAR结构）
            elif isinstance(data, dict):
                available = data.get('available', data.get('credits', {}).get('available', 0))
                total = data.get('total', data.get('credits', {}).get('total', 0))
            
            # 方案3：从HAR已知路径
            credits_data = data.get('data', {}) if data.get('success') else data
            available = int(credits_data.get('available', credits_data.get('credits', {}).get('available', 0) or 0))
            total = int(credits_data.get('total', credits_data.get('credits', {}).get('total', 0) or 0))
            
            # 输出结果
            result = f"""
🎯 积分概览 (https://v2.loomi.live/zh/profile#user)
━━━━━━━━━━━━━━━━━━━━━━
💰 可用积分: {available:,}
💎 总积分:   {total:,}

📅 获取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📧 账号:     {email}
🔢 运行ID:   {run_id}
━━━━━━━━━━━━━━━━━━━━━━
            """
            
            print(result)
            logger.info(f"解析成功 - 可用:{available}, 总计:{total}")
            
            # 保存报告
            with open("credits_report.txt", "w", encoding="utf-8") as f:
                f.write(result)
                f.write(f"\n\n--- 原始数据 ---\n{json.dumps(data, indent=2, ensure_ascii=False)}")
            
            return {"available": available, "total": total, "success": True}
        else:
            print(f"❌ API失败: {resp.status_code}")
            return {"success": False}
            
    except Exception as e:
        logger.error(f"❌ 异常: {str(e)}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    if os.getenv('GITHUB_ACTIONS'):
        result = get_loomi_credits()
        exit(0 if result.get('success') else 1)
    else:
        get_loomi_credits()
