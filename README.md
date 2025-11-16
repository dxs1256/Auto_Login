# ✨ 自用全自动签到与通知系统 ✨

**🚀 驱动：GitHub Actions | 🤖 核心：Python/Node.js | 🔔 通知：Telegram**

本仓库用于自动化执行各类网站和服务的日常签到和保活任务。所有账号和通知信息均通过 GitHub Secrets 安全管理。

---

## 🎯 任务列表 (Services)

| 网站/服务 | 脚本文件 | 核心功能 | 运行频率 (UTC) | 状态 | 环境变量 (Secrets) |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **福利吧** | `fuliba.py` | 自动签到, 检查 Cookie 有效性 | `0 18,22 * * *` (每日 02:00, 06:00 HKT) | ✅ 稳定运行 | `FUBA`, `FUBAUN` |
| **Netlib** | `login.js` | Playwright 登录保活 | `0 20 * * 6` (每周六 20:00 执行) | ✅ 稳定运行 | `NETLIB_ACCOUNTS` |
| **Koyeb** | `koyeb.py` | Playwright 登录保活 | `0 20 * * 6` (每周六 20:00 执行) | ✅ 稳定运行 | `KOYEB_ACCOUNTS` |

---

## ⚙️ 部署与配置

所有敏感信息都必须作为 **GitHub Secrets** 配置在您的仓库中。

### 1. Telegram 通知配置

| Secret 名称 | 作用 |
| :--- | :--- |
| `TG_BOT_TOKEN` | 接收通知的 Telegram Bot 的 HTTP API Token。|
| `TG_CHAT_ID` | 接收通知的个人/群组聊天 ID。|

### 2. 网站账号配置

| Secret 名称 | 对应脚本 | 格式说明 |
| :--- | :--- | :--- |
| `FUBA` | `fuliba.py` | 完整的登录 Cookie 字符串，用于保持会话。|
| `FUBAUN` | `fuliba.py` | 网站登录用户名，用于 Cookie 有效性验证。|
| `NETLIB_ACCOUNTS` | `login.js` | 格式: `用户名:密码`，支持逗号或分号分隔多个账号。|
| `KOYEB_ACCOUNTS` | `koyeb.py` | 格式: `用户名:密码`，支持逗号或分号分隔多个账号。|

---

## 💻 脚本技术栈

*   **Python 脚本 (`.py`)**: 使用 `requests` (HTTP 请求) 和 `BeautifulSoup4` (HTML 解析) 确保签到逻辑的稳定性和健壮性。
*   **Node.js 脚本 (`.js`)**: 使用 `Playwright` 库模拟真实浏览器行为，处理复杂的登录和页面交互，适用于保活任务。

---

## 🔔 工作流文件 (`.github/workflows/*.yml`)

| 文件名 | 触发方式 |
| :---: | :---: |
| `Fuliba_login.yml` | 定时 (`0 18,22 * * *`) 和 手动触发 |
| `Netlib_login.yml` | 定时 (`25 9 */30 * *`) 和 手动触发 |
| `Koyeb_login.yml` | 定时 (`25 9 */30 * *`) 和 手动触发 |

---

## ⚠️ 免责声明 (Disclaimer)

本仓库代码仅供个人学习、测试和交流之用，请勿用于非法用途。使用本脚本可能违反相关网站的用户协议，由此产生的一切后果由使用者自行承担。请务必妥善保管您的 GitHub 账号和 Secrets，确保敏感信息的安全。
