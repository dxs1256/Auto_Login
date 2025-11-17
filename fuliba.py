import requests
import re
import os
import sys
from datetime import datetime

# --- 配置区：从环境变量读取敏感信息 ---
SESSION_COOKIE = os.environ.get('FUBA')
ACCOUNT_USERNAME = os.environ.get('FUBAUN', '未知用户') 
SOCKS5_PROXY_URL = os.environ.get('SOCKS5_PROXY_URL')

REFERER_URL = "https://www.wnflb2023.com/" 
CHECKIN_URL = "https://www.wnflb2023.com/plugin.php"

# 通用请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "Referer": REFERER_URL, 
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded"
}

# --- 函数：初始化 Session 并配置代理 ---
def initialize_session():
    """初始化 requests Session 并配置 SOCKS5 代理"""
    session = requests.Session()
    
    if SOCKS5_PROXY_URL:
        # 验证 requests-socks 依赖是否安装，并配置代理
        try:
            # 尝试导入 requests-socks 模块
            import socks
        except ImportError:
            # 如果导入失败，则依赖未安装
            print("!!! 错误：检测到 SOCKS5 代理，但缺少 requests[socks] 依赖。")
            print("!!! 请在 GitHub Actions 中运行 'pip install requests[socks]' !!!")
            sys.exit(1)

        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 正在使用 SOCKS5 代理...")
        
        # 🎯 关键修复：移除 'socks.set_socket(socks.create_connection)' 这一行
        
        session.proxies = {
            'http': SOCKS5_PROXY_URL,
            'https': SOCKS5_PROXY_URL
        }
        
    return session

# --- 函数：动态获取 Formhash ---
def get_formhash(session):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 账号: {ACCOUNT_USERNAME} | 正在尝试获取最新的 Formhash...")
    try:
        current_headers = HEADERS.copy()
        current_headers['Cookie'] = SESSION_COOKIE
        
        response = session.get(REFERER_URL, headers=current_headers, timeout=15)
        match = re.search(r'formhash=([0-9a-fA-F]{8,})', response.text) 
        
        if match:
            formhash = match.group(1)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 账号: {ACCOUNT_USERNAME} | 成功获取 Formhash: {formhash}")
            return formhash
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 账号: {ACCOUNT_USERNAME} | 错误：未能在页面内容中找到 Formhash。")
            return None
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 账号: {ACCOUNT_USERNAME} | 致命错误：访问 {REFERER_URL} 时发生网络错误或代理连接失败: {e}")
        return None

# --- 函数：执行签到操作 ---
def perform_checkin():
    session = initialize_session() 
    formhash = get_formhash(session)
    if not formhash:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 账号: {ACCOUNT_USERNAME} | 签到失败：无法获取 Formhash。")
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
        
        checkin_response = session.post(
            CHECKIN_URL, 
            data=payload,  
            headers=current_headers, 
            timeout=15
        )

        print(f"[{datetime.now().strftime('%H:%M:%S')}] 账号: {ACCOUNT_USERNAME} | 服务器响应状态码: {checkin_response.status_code}")
        
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
