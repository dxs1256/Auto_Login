# Auto-R4S - ImmortalWrt 自动构建

**专为 FriendlyARM NanoPi R4S 设计的 ImmortalWrt 固件自动编译工具**

![GitHub Actions](https://img.shields.io/badge/Engine-GitHub_Actions-blue?logo=githubactions)
![Target](https://img.shields.io/badge/Target-NanoPi%20R4S-orange)
![Platform](https://img.shields.io/badge/Platform-rockchip%20armv8-green)

---

## 🌟 核心亮点

- **全自动编译**：基于 GitHub Actions，无需本地环境，一键触发云端编译
- **智能版本选择**：支持 `latest` 自动获取最新版 24.10.x，或手动指定具体版本
- **PPPoE 预配置**：可直接在编译时填入宽带账号密码，固件刷入即用
- **自定义管理 IP**：支持设置默认后台地址（默认 192.168.1.1）
- **Docker 可选**：按需集成 Docker，扩大子网范围防止容器断网
- **第三方插件**：自动集成 [wukongdaily/store](https://github.com/wukongdaily/store) 仓库的 arm64 插件
- **镜像源加速**：自动切换 Cernet 教育网镜像，避免下载失败
- **网口自动识别**：首次开机自动识别 WAN/LAN 物理网口，无需手动配置

---

## 📋 构建参数说明

| 参数名 | 说明 | 默认值 |
| :--- | :--- | :--- |
| `luci_version` | LuCI 版本，选 `latest` 自动获取最新 24.10.x | `latest` |
| `profile` | 固定机型：`friendlyarm_nanopi-r4s` | `friendlyarm_nanopi-r4s` |
| `custom_router_ip` | 管理后台地址 | `192.168.1.1` |
| `rootfs_partsize` | Rootfs 分区大小 (MB) | `3072` |
| `include_docker` | 是否集成 Docker | `yes` |
| `enable_pppoe` | 是否配置 PPPoE 拨号 | `yes` |
| `pppoe_account` | 宽带账号（启用 PPPoE 时必填） | `071900263467` |
| `pppoe_password` | 宽带密码（启用 PPPoE 时必填） | `123456` |

---

## 🚀 快速开始

### 1. Fork 仓库

点击右上角 **Fork** 按钮，将此仓库复制到你自己的 GitHub 账号下。

### 2. 触发编译

1. 进入 **Actions** 标签页
2. 选择 `build-rockchip-nanopi-r4s` 工作流
3. 点击 **Run workflow**
4. 填写你想要的参数（版本号、IP、PPPoE 等）
5. 点击 **Run workflow** 开始编译

### 3. 下载固件

编译完成后会自动创建 Release，在 **Releases** 页面下载：

- `*.img.gz` - 完整的固件镜像
- `Plugin-list.txt` - 已安装的插件清单
- `router-info.md` - 后台登录信息

---

## ⚙️ 架构说明

```
Auto-R4S
├── .github/
│   └── workflows/
│       ├── build-rockchip-nanopi-r4s.yml   # 主编译工作流
│       └── Cleanup-Old-History.yml          # 历史清理工作流
├── rockchip/
│   ├── build24.sh          # 主构建脚本（在 Docker 内执行）
│   └── imm.config          # ImmortalWrt 配置文件
├── shell/
│   ├── prepare-packages.sh  # 第三方包解压整理
│   ├── switch_repository.sh # 切换镜像源
│   └── custom-packages.sh   # 自定义插件列表
├── files/
│   └── etc/uci-defaults/
│       └── 99-custom.sh    # 首次开机初始化脚本
├── arch/
│   └── arch.conf           # opkg 架构配置
└── README.md
```

---

## 🛠️ 核心脚本解析

### build24.sh - 主构建脚本

在 ImmortalWrt 官方 Docker 镜像 `immortalwrt/imagebuilder:rockchip-armv8-openwrt-24.10.x` 内执行：

1. **动态生成 PPPoE 配置** - 根据 GitHub Actions 传入的参数生成 `/etc/config/pppoe-settings`
2. **同步第三方插件仓库** - 克隆 `wukongdaily/store`，解压 `.run` 文件提取 `.ipk`
3. **创建 opkg 占位脚本** - 修复 25.12.0+ 版本构建错误
4. **定义安装包列表** - 排除冲突包（dnsmasq 重复问题），添加基础工具和插件
5. **多线程编译** - 使用 `make image -j$(nproc)` 跑满 CPU

### 99-custom.sh - 首次开机初始化

固件首次启动时自动执行：

```bash
# 1. DNS 优化 - 解决安卓 TV 时间同步问题
uci set dhcp.@domain[-1].name=time.android.com
uci set dhcp.@domain[-1].ip=203.107.6.88

# 2. 自动识别物理网口 - 第一个为 WAN，其余为 LAN
wan_ifname=$(echo "$ifnames" | awk '{print $1}')
lan_ifnames=$(echo "$ifnames" | cut -d ' ' -f2-)

# 3. 应用 PPPoE 配置 - 读取 build24.sh 生成的配置文件
if [ "$enable_pppoe" = "yes" ]; then
    uci set network.wan.proto='pppoe'
    uci set network.wan.username="$pppoe_account"
    uci set network.wan.password="$pppoe_password"
fi

# 4. Docker 防火墙规则 - 扩大子网范围
config zone 'docker'
  list subnet '172.16.0.0/12'

# 5. 修改系统信息 - 在系统概览页显示
DISTRIB_DESCRIPTION='Packaged by Github Actions'
```

---

## 📦 默认集成的插件

### 必装插件

| 插件名 | 说明 |
| :--- | :--- |
| `luci-app-adguardhome` | 去广告 |
| `luci-i18n-passwall-zh-cn` | 代理工具 |
| `luci-app-turboacc` | 网络加速 (Turbo ACC) |
| `luci-i18n-aria2-zh-cn` | 下载工具 |
| `luci-i18n-diskman-zh-cn` | 磁盘管理 |
| `luci-i18n-openlist-zh-cn` | 文件列表 |
| `luci-i18n-samba4-zh-cn` | SMB 共享 |
| `luci-theme-argon` | Argon 主题 |
| `luci-i18n-firewall-zh-cn` | 防火墙中文 |
| `dnsmasq-full` | 全功能 DNS |

### 第三方仓库插件

自动从 `wukongdaily/store` 克隆 `run/arm64/*` 目录的插件包，支持 `.run` 解压和 `.ipk` 整理。

---

## 🔧 自定义插件

编辑 `shell/custom-packages.sh`，取消注释即可添加：

```bash
# 代理相关
CUSTOM_PACKAGES="$CUSTOM_PACKAGES luci-app-ssr-plus"
CUSTOM_PACKAGES="$CUSTOM_PACKAGES luci-app-passwall2"

# 主题
CUSTOM_PACKAGES="$CUSTOM_PACKAGES luci-theme-kucat"

# sirpdboy 系列
CUSTOM_PACKAGES="$CUSTOM_PACKAGES luci-app-partexp"       # 分区扩容
CUSTOM_PACKAGES="$CUSTOM_PACKAGES luci-app-netspeedtest"  # 网络测速
CUSTOM_PACKAGES="$CUSTOM_PACKAGES luci-app-advancedplus"  # 进阶设置
```

**注意**：硬路由闪存空间有限，添加过多插件可能导致固件过大或编译失败。

---

## 🗑️ 清理历史编译

触发 `Cleanup-Old-History.yml` 工作流，可删除旧的 Workflow 运行记录：

- 参数 `keep_days`：保留最近多少天（默认 1 天）
- 用途：节省 GitHub Actions 存储空间

---

## ⚠️ 注意事项

1. **PPPoE 账号密码** 会直接写入固件，请勿使用生产环境的真实账号测试
2. **固件大小** 超过 3072MB 可能导致编译失败，可适当调整 `rootfs_partsize`
3. **Docker 防火墙** 会在首次开机时自动注入 `172.16.0.0/12` 子网规则
4. **网口识别** 依赖 `/sys/class/net/` 的物理网卡枚举，确保设备有 eth/en 前缀的网卡

---

## 📡 固件信息

| 项目 | 值 |
| :--- | :--- |
| 后台地址 | 编译时设置的 IP（默认 192.168.1.1） |
| 用户名 | `root` |
| 密码 | 无（首次登录需自行设置） |
| 固件版本 | ImmortalWrt 24.10.x |
| 内核版本 | 6.6.x（根据编译版本而定） |
| 系统标识 | `Packaged by Github Actions` |

---

## 🛡️ 技术细节

### 版本号解析逻辑

```bash
# 当用户选择 latest 时，自动从 Docker Hub 查询最新版本
LATEST_VER=$(curl -sL "https://hub.docker.com/v2/repositories/immortalwrt/imagebuilder/tags/?page_size=100" | \
jq -r '.results[].name' | \
grep -E '.*-openwrt-24\.10\.[0-9]+$' | \
sed -E 's/.*-openwrt-(24\.10\.[0-9]+)$/\1/' | \
sort -V | \
tail -n1)

# 防呆机制 - 获取失败时回退到 24.10.5
if [[ -z "$LATEST_VER" ]]; then
  LATEST_VER="24.10.5"
fi
```

### 镜像源切换

```bash
# 官方源 → Cernet 教育网镜像
OFFICIAL="https://downloads.immortalwrt.org"
MIRROR="https://mirrors.cernet.edu.cn/immortalwrt"
sed -i "s#${OFFICIAL}#${BASE_URL}#g" repositories.conf
```

---

## ⚠️ 免责声明

1. **个人自用**：本仓库所有代码仅供个人学习、测试与合法自用
2. **合规使用**：请严格遵守各平台服务条款，禁止用于任何商业或非法用途
3. **风险自负**：刷写固件有风险，一切风险与后果由使用者自行承担
4. **安全须知**：作者无法访问你的 GitHub Secrets，配置信息安全

---

> **一键 Fork + 触发 Actions 即可开始编译，告别本地环境！**

*最后更新: 2026-06-13*
