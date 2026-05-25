# 🚀 快速部署指南

## 一分钟部署完成

### 步骤 1: 注册 PushPlus（30 秒）

1. 微信扫码关注"推送加"公众号
2. 发送消息"token"获取你的 Token
3. 复制 Token 备用

### 步骤 2: 配置 GitHub Secret（30 秒）

```bash
# 使用 GitHub CLI（推荐）
gh secret set PUSHPLUS_TOKEN --body "你的 PushPlus token"

# 或者在 GitHub 网站操作：
# 1. 访问仓库 -> Settings -> Secrets and variables -> Actions
# 2. New repository secret
#    Name: PUSHPLUS_TOKEN
#    Value: 你的 token
```

### 步骤 3: 推送代码（30 秒）

```bash
# 初始化仓库
git init
git add .
git commit -m "Initial commit: OpenRouter monitor with PushPlus"

# 创建远程仓库（在 GitHub）
# 访问 https://github.com/new
# 创建仓库：openrouter-model-monitor

# 关联并推送
git remote add origin https://github.com/你的用户名/openrouter-model-monitor.git
git branch -M main
git push -u origin main
```

### 步骤 4: 启用 Actions（30 秒）

1. 访问仓库的 **Actions** 标签
2. 点击 **I understand my workflows, go ahead and enable them**
3. 点击 **Run workflow** 手动测试一次

---

## 检查清单

- [ ] PushPlus token 已配置
- [ ] 代码已推送到 GitHub
- [ ] Actions 已启用
- [ ] 手动测试运行成功
- [ ] 微信公众号收到测试消息

---

## 使用方式

### 自动监控

- **频率**: 每小时自动运行一次（UTC 时间）
- **通知**: 发现新模型时通过微信公众号推送

### 手动触发

1. 访问仓库 Actions 标签
2. 选择 "OpenRouter Model Monitor"
3. 点击 "Run workflow"

### 查看运行日志

1. Actions -> 最近的运行记录
2. 点击查看详细日志
3. 搜索 "PushPlus" 查看推送结果

---

## 文件说明

```
.
├── .github/
│   └── workflows/
│       └── monitor.yml          # GitHub Actions 工作流
├── openrouter-monitor-pushplus.py  # 监控脚本
├── openrouter_models_cache.json    # 模型缓存（自动生成）
└── README.md                       # 说明文档
```

---

## 自定义配置

### 修改监控频率

编辑 `.github/workflows/monitor.yml`:

```yaml
on:
  schedule:
    - cron: '0 */2 * * *'  # 每 2 小时一次
    - cron: '0 9 * * *'    # 每天早上 9 点 (UTC)
```

### 群组推送

1. 创建 PushPlus 群组
2. 获取群组编码
3. 配置 Secret:

```bash
gh secret set PUSHPLUS_TOPIC --body "你的群组编码"
```

---

## 故障排查

### 没收到推送？

1. 检查 Secret 是否正确配置
2. 查看 Actions 运行日志
3. 确认 PushPlus token 有效

### 推送失败？

查看日志中的错误信息：
- `invalid token`: Token 无效，重新获取
- `network error`: 网络问题，重试即可
- `frequency limit`: 频率限制，减少监控频率

---

## 完成！🎉

现在你将通过微信公众号及时收到新模型通知！

访问仓库：https://github.com/你的用户名/openrouter-model-monitor
