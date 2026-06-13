
**自用全自动签到、保活与监控系统 · 基于 GitHub Actions 驱动**

![GitHub Actions](https://img.shields.io/badge/Engine-GitHub_Actions-blue?logo=githubactions)
![Language](https://img.shields.io/badge/Language-Python%20%7C%20Node.js-orange)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 🌟 核心亮点

- **零成本运行**：完全依托 GitHub Actions，无需购买服务器或 VPS，7x24 小时自动巡航。
- **多账号并发**：支持多平台多账号同时管理，配置简单，扩展性强。
- **双通道通知**：深度适配 **Telegram** 与 **PushPlus (微信)**，精美排版，确保每一条状态都能精准触达。
- **智能容错机制**：内置多域名自动切换（福利吧）、失败重试（火烧云）、状态掩码脱敏等高级特性。
- **模块化设计**：每个任务独立脚本与工作流，互不干扰，按需开关。

---

## 📋 任务矩阵 (Service Matrix)

| 服务/平台 | 核心脚本 | 功能特性 | 运行频率 (北京时间) | 推荐 Secrets |
| :--- | :--- | :--- | :--- | :--- |
| **Koyeb** | `koyeb.py` | ☁️ API 级账户状态监控与活跃度检查 | 每周六 00:00 | `KOYEB_TOKENS` |
| **福利吧** | `fuliba.js` | 🎫 自动签到，6 域名容错，提取连签天数/排名 | 每天 00:00 / 02:00 | `FULI_COOKIE` |
| **Office 365 E5** | `e5.py` | 🏢 多租户订阅状态监控与续期提醒 | 每天 00:00 | `TENANT_ID`, `CLIENT_SECRET` 等 |
| **火烧云监控** | `daily_check.js` | 🌅 监控日落/日出概率，超阈值自动预警 | 每 3 小时 | `SUNSET_CITY` |
| **仓库清理** | `cleanup.yml` | 🧹 自动删除旧 Workflow 记录，节省空间 | 每天 11:00 | (内置) |

---

## 🚀 快速部署

只需简单三步，即可一键开跑：

### 1. Fork 仓库
点击右上角的 **Fork** 按钮，将此仓库复制到你自己的 GitHub 账号下。

### 2. 配置 Secrets
进入你 Fork 后的仓库 -> `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`。
根据你想运行的服务，添加对应的环境变量（详见下方说明）。

### 3. 开启 Actions
如果 Actions 默认是关闭的，请前往仓库的 **Actions** 标签页，点击 `I understand my workflows, go ahead and enable them` 开启。

---

## ⚙️ 环境变量配置详解

所有敏感信息均通过 GitHub Secrets 安全注入，绝不硬编码。

### 📢 通用通知通道 (强烈建议配置)
| Secret 名称 | 作用 |
| :--- | :--- |
| `TG_BOT_TOKEN` | Telegram Bot 的 Token |
| `TG_CHAT_ID` | 接收通知的聊天 ID（私聊或群组均可） |
| `PUSHPLUS_TOKEN` | PushPlus 推送 Token（支持公众号通知） |

### 📦 各服务专用 Secrets

| Secret 名称 | 对应脚本 | 格式说明 |
| :--- | :--- | :--- |
| `KOYEB_TOKENS` | `koyeb.py` | JSON 数组，如 `[{"token":"abc"},{"token":"def"}]` |
| `FULI_COOKIE` | `fuliba.js` | 多个账号 Cookie 用 `@` 分隔：`cookie1@cookie2` |
| `TENANT_ID` / `CLIENT_ID` / `CLIENT_SECRET` | `e5.py` | 微软 API 凭据。多账号可追加后缀 `_2`, `_3` (如 `TENANT_ID_2`) |
| `SUNSET_CITY` | `daily_check.js` | 监控城市，如 `广东省 - 深圳` (默认值) |
| `SUNSET_THRESHOLD` | `daily_check.js` | 触发报警的概率阈值，默认 `0.5` |

---

## 🛠️ 脚本技术栈与细节

- **Node.js 脚本**：基于 `axios` 实现 HTTP 请求，支持重试机制与智能通知排版。
- **Python 脚本**：使用 `requests` 实现轻量级、高并发的 API 交互。
- **智能通知排版**：
  - **Telegram**：采用 HTML 标签与等宽代码块混合的仪表盘排版。
  - **PushPlus**：自动将 Markdown 或文本转换为适配微信端的 HTML 样式（带高亮与分割线）。

---

## ⚠️ 免责声明 (Disclaimer)

1. **个人自用**：本仓库所有代码仅供个人学习、测试与合法自用。
2. **合规使用**：请严格遵守各平台服务条款，禁止用于任何商业或非法用途。
3. **风险自负**：一切风险与后果由使用者自行承担，作者不承担任何连带责任。
4. **安全须知**：作者无法访问你的 Secrets，账号安全完全由 GitHub 机制保障。

---

> **一键 Fork + 配置 Secrets 即可开跑，解放双手，从此躺平！**

*最后更新: 2026-06-13*
