# usst-e-fees

上海理工大学宿舍电费监测服务。它根据 WeLink 内宿舍管理系统的请求，定时查询宿舍插电照明和空调剩余电费；当电费低于配置阈值时发送通知。

## 功能

- 查询当前宿舍、照明电费/电量、空调电费/电量
- 支持照明和空调分别设置提醒阈值
- 支持 Bark、Gotify、邮件、控制台通知
- 支持多个账号
- 支持定时监控、告警冷却，避免重复刷屏
- 支持从 Loon 抓包导入请求头

## 快速开始

开发环境运行：

```bash
uv sync
uv run usst-e-fees --help
```

安装为本机命令后，可以不加 `uv run` 直接调用：

```bash
uv tool install --editable .
usst-e-fees --help
```

生成配置文件：

```bash
usst-e-fees init-config
usst-e-fees where
```

从抓包导入凭据。推荐导入 `GetDormElectricityFees` 这条请求的 `request_header_raw.txt`：

```bash
usst-e-fees auth-import "D:\path\to\request_header_raw.txt"
```

长期监控还需要导入 WeLink 的授权码刷新请求头。请在 Loon 抓包里找到这条请求并导入它的 `request_header_raw.txt`：

```text
POST https://api.welink.huaweicloud.com/mcloud/mag/ProxyForText/ssoauth/v1/code
```

```bash
usst-e-fees auth-import "D:\path\to\ssoauth_request_header_raw.txt"
usst-e-fees auth-refresh
```

也可以手动保存：

```bash
usst-e-fees auth-set --weaccess-token "X-Weaccess-Token" --hw-code "x-hw-code" --cookie "ASP.NET_SessionId=...;https=0" --welink-cookie "token=...;cdn_token=..."
```

测试查询：

```bash
usst-e-fees poll-once
```

带通知测试：

```bash
usst-e-fees notify-test
usst-e-fees poll-once --notify
```

开始监控：

```bash
usst-e-fees watch
```

## 配置示例

默认配置文件位置：

| 系统 | 配置文件 |
| --- | --- |
| Windows | `%LOCALAPPDATA%\usst-e-fees\config.yaml` |
| Linux / VPS | `~/.config/usst-e-fees/config.yaml` |

阈值配置：

```yaml
thresholds:
  lighting_money: 20.0
  aircon_money: 20.0
```

Bark 通知：

```yaml
notify:
  bark:
    enabled: true
    server: https://api.day.app
    key: 你的 Bark key
```

多账号：

```yaml
accounts:
  - id: main
    name: 我的账号
    enabled: true
    session_file: sessions/main.json
  - id: roommate
    name: 室友
    enabled: true
    session_file: sessions/roommate.json
```

导入不同账号凭据：

```bash
usst-e-fees auth-import ".\main_request_header_raw.txt" --account main
usst-e-fees auth-import ".\roommate_request_header_raw.txt" --account roommate
```

监控所有启用账号：

```bash
usst-e-fees watch --all
```

## 抓包接口来源

抓包中电费页面为：

```text
GET http://ssgl.usst.edu.cn/SSGL/StuMobile/StuView/VoucherCenter.html
```

页面查询接口为：

```text
GET http://ssgl.usst.edu.cn/api/Voucher/GetDormElectricityFees?IsLoadData=false
```

接口返回字段包括 `SurplusZMMoney`、`SurplusZM`、`SurplusKTMoney`、`SurplusKT`、`SSDZ`、`SSId` 等。

WeLink 的 `x-hw-code` 和宿舍系统 Cookie 会过期；导入 `ssoauth/v1/code` 请求头后，工具会自动刷新 `x-hw-code` 和宿舍系统会话。如果 WeLink Cookie 也过期，再重新抓包并执行 `auth-import`。
