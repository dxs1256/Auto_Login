import requests
import re
import os
from datetime import datetime

# --- 配置区：从环境变量读取敏感信息 ---
SESSION_COOKIE = os.environ.get('FUBA')
ACCOUNT_USERNAME = os.environ.get('FUBAUN', '未知用户') 
REFERER_URL = "https://www.wnflb2023.com/" 
CHECKIN_URL = "https://www.wnflb2023.com/plugin.php"

# 通用请求头
HEADERS = {
    # 🚨 关键修改：使用用户提供的完整 User-Agent
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "Referer": REFERER_URL, 
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded"  # 模拟表单 POST 提交
}

# --- 函数：动态获取 Formhash ---
def get_formhash(session):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 账号: {ACCOUNT_USERNAME} | 正在尝试获取最新的 Formhash...")
    try:
        current_headers = HEADERS.copy()
        current_headers['Cookie'] = SESSION_COOKIE
        
        response = session.get(REFERER_URL, headers=current_headers, timeout=10)
        match = re.search(r'formhash=([0-9a-fA-F]{8,})', response.text) 
        
        if match:
            formhash = match.group(1)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 账号: {ACCOUNT_USERNAME} | 成功获取 Formhash: {formhash}")
            return formhash
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 账号: {ACCOUNT_USERNAME} | 错误：未能在页面内容中找到 Formhash。")
            return None
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 账号: {ACCOUNT_USERNAME} | 错误：访问 {REFERER_URL} 时发生网络错误: {e}")
        return None

# --- 函数：执行签到操作 ---
def perform_checkin():
    session = requests.Session()
    formhash = get_formhash(session)
    if not formhash:
        print(f"[{datetime.now().strftime('%H:%MZ')}] 账号: {ACCOUNT_USERNAME} | 签到失败：无法获取 Formhash。")
        return

    payload = {
        "id": "fx_checkin:checkin",
        "formhash": formhash,
        "infloat": "yes",
        "handlekey": "fx_checkin",
        "inajax": "1",
        "ajaxtarget": "fwin_content_fx_checkin"
    }
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 账号: {ACCOUNT_USERNAME} | 正在发送 POST 签到请求...")
    try:
        current_headers = HEADERS.copy()
        current_headers['Cookie'] = SESSION_COOKIE
        
        # 使用 POST 请求和 data=payload 发送
        checkin_response = session.post(
            CHECKIN_URL, 
            data=payload,  
            headers=current_headers, 
            timeout=10
        )

        print(f"[{datetime.now().strftime('%H:%M:%S')}] 账号: {ACCOUNT_USERNAME} | 服务器响应状态码: {checkin_response.status_code}")
        
        # 5. 分析响应内容 (调试模式：打印原始响应)
        response_text = checkin_response.text
        
        print("--- 服务器原始响应内容 START ---")
        print(response_text)
        print("--- 服务器原始响应内容 END ---")

        if "签名出错" in response_text or "请重新登陆" in response_text:
            print("❌ 签到失败：会话过期或签名错误。")
        elif "已签到" in response_text or "恭喜" in response_text:
            print("✅ 签到成功！")
        else:
            print("❓ 签到完成，但无法确定结果。")


    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 账号: {ACCOUNT_USERNAME} | 致命错误：执行签到请求时发生网络错误: {e}")

# --- 主程序入口 ---
if __name__ == "__main__":
    if not SESSION_COOKIE:
        print("!!! 运行错误：未找到 COOKIE。请确保 FUBA 环境变量已正确设置。!!!")
    else:
        perform_checkin()
