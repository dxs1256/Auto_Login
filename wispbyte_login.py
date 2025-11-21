import requests
import os

# 直接使用你给的 cookie
session = requests.Session()
session.cookies.set("connect.sid", "s:N1IxBmuyPIzaQVWpvTdDcP8bhLCxkJOk.nw3yb5Jj3SC4+HN4YktFcnlDjIphedQVX3SXzZGo7X8", domain="wispbyte.com")
session.cookies.set("cookiesAccepted", "true", domain="wispbyte.com")
session.cookies.set("analyticsEnabled", "true", domain="wispbyte.com")
session.cookies.set("advertisingEnabled", "true", domain="wispbyte.com")

session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})

# 测试是否登录成功
r = session.get("https://wispbyte.com/client/api/user")
print(r.json())   # 能打印出你的用户名、邮箱、服务器数量等信息 → 就代表 100% 成功

# 示例：列出你所有的服务器
servers = session.get("https://wispbyte.com/client/api/servers").json()
for s in servers:
    print(f"服务器ID: {s['id']}  名称: {s['name']}  状态: {s['status']}")
