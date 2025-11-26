# 自用全自动签到与通知系统

**驱动：GitHub Actions | 核心：Python/Node.js | 通知：Telegram + PushPlus**

本仓库自动化执行各类网站和服务的日常签到/保活任务，所有账号和通知信息均通过 GitHub Secrets 安全管理。

---

## 任务列表 (Services)

| 网站/服务          | 脚本文件         | 核心功能                     | 建议运行频率 (UTC)               | 状态        | 环境变量 (Secrets)                          |
|--------------------|------------------|------------------------------|----------------------------------|-------------|---------------------------------------------|
| **Netlib**         | `login.js`       | Playwright 自动登录保活       | `0 12 * * *`（每天 20:00 北京时间）<br>或每周 `0 20 * * 6` | 稳定运行    | `NETLIB_ACCOUNTS`                           |
| **Koyeb**          | `koyeb.py`       | API 自动登录保活             | `0 1 * * *`（每天 09:00 北京时间） | 稳定运行    | `KOYEB_ACCOUNTS`（JSON 数组）               |
| **福利吧（多站点）**| `fuliba.js`      | 自动签到 + 多域名容错         | `0 2 * * *`（每天 10:00 北京时间） | 稳定运行    | `FULI_COOKIE`                               |
| **Wispbyte**       | `wispbyte.py`    | Cookie 保活 + 用户名提取      | `0 3 * * *`（每天 11:00 北京时间） | 稳定运行    | `WISPBYTE_COOKIE_STRING`、`SOCKS5_PROXY`（可选） |
| **Office 365 E5**  | `e5.py`          | 多租户订阅状态监控与续期提醒   | `0 4 * * *`（每天 12:00 北京时间） | 稳定运行    | `TENANT_ID`、`CLIENT_ID`、`CLIENT_SECRET`<br>（多账号后缀 _2、_3…）|

---

## 部署与配置

所有敏感信息都必须作为 **GitHub Repository Secrets** 配置。

### 1. 通用通知配置（强烈建议都配上）

| Secret 名称         | 作用                                      |
|---------------------|-------------------------------------------|
| `TG_BOT_TOKEN`      | Telegram Bot 的 Token                     |
| `TG_CHAT_ID`        | 接收通知的聊天 ID（私聊/群组均可）         |
| `PUSHPLUS_TOKEN`    | PushPlus 推送 Token（微信/公众号通知）     |

### 2. 各服务专用配置

| Secret 名称                  | 对应脚本         | 格式说明                                                                 |
|-----------------------------|------------------|--------------------------------------------------------------------------|
| `NETLIB_ACCOUNTS`           | `login.js`       | `用户名1:密码1,用户名2:密码2`（逗号或分号分隔）                           |
| `KOYEB_ACCOUNTS`            | `koyeb.py`       | JSON 数组，例如：`[{"email":"a@b.com","password":"xxx"}]`                |
| `FULI_COOKIE`               | `fuliba.js`      | 多个账号用 `@` 分隔，例如：`cookie1@cookie2@cookie3`                     |
| `WISPBYTE_COOKIE_STRING`    | `wispbyte.py`    | 多个账号 Cookie 用 `&` 分隔（完整 Cookie 字符串）                        |
| `TENANT_ID` / `CLIENT_ID` / `CLIENT_SECRET` | `e5.py` | 主账号凭据<br>多账号依次使用 `TENANT_ID_2`、`CLIENT_ID_2`、`CLIENT_SECRET_2` 等 |

### 3. 可选配置

| Secret 名称       | 作用                        |
|-------------------|-----------------------------|
| `SOCKS5_PROXY`    | 为 Wispbyte 等脚本提供 SOCKS5 代理（格式：`user:pass@ip:port` 或 `ip:port`） |

---

## 建议的工作流文件 (.github/workflows/)

| 服务          | 推荐文件名                | Cron 示例（北京时间）               |
|---------------|---------------------------|-------------------------------------|
| Netlib        | `netlib.yml`              | `0 12 * * *`   （每天 20:00）       |
| Koyeb         | `koyeb.yml`               | `0 1 * * *`    （每天 09:00）       |
| 福利吧        | `fuliba.yml`              | `0 2 * * *`    （每天 10:00）       |
| Wispbyte      | `wispbyte.yml`            | `0 3 * * *`    （每天 11:00）       |
| Office 365 E5 | `e5-monitor.yml`          | `0 4 * * *`    （每天 12:00）       |

> 所有脚本均支持手动 workflow_dispatch 触发，方便调试。

---

## 脚本技术栈

- **Python 脚本**：`requests` 实现轻量、稳定签到/查询
- **Node.js 脚本**：`Playwright` + `axios` 模拟真实浏览器，应对复杂登录
- **通知方式**：Telegram + PushPlus（微信）双通道，确保不错过任何消息

---

## 免责声明 (Disclaimer)

本仓库所有代码仅供个人学习、测试与合法自用。请严格遵守各网站服务条款，禁止用于任何商业或非法用途。  
一切风险与后果由使用者自行承担，作者不承担任何责任。

---

**一键 Fork + 配置 Secrets 即可开跑，解放双手，从此躺平！**
