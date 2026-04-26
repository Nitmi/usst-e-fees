# usst-electricity

上海理工大学宿舍电费监测服务。它根据 WeLink 内宿舍管理系统的请求，定时查询宿舍插电照明和空调剩余电费；当电费低于配置阈值时发送通知。

## 功能

- 查询当前宿舍、照明电费/电量、空调电费/电量
- 支持照明和空调分别设置提醒阈值
- 支持 Bark、Gotify、邮件、控制台通知
- 支持多个账号
- 支持定时监控、告警冷却，避免重复刷屏
- 支持从 Loon 抓包导入请求头

## 快速开始

安装依赖并查看命令：

```bash
uv sync
uv run usst-electricity --help
```

生成配置文件：

```bash
uv run usst-electricity init-config
uv run usst-electricity where
```

从抓包导入凭据。推荐导入 `GetDormElectricityFees` 这条请求的 `request_header_raw.txt`：

```bash
uv run usst-electricity auth-import "D:\path\to\request_header_raw.txt"
```

也可以手动保存：

```bash
uv run usst-electricity auth-set --weaccess-token "X-Weaccess-Token" --hw-code "x-hw-code" --cookie "ASP.NET_SessionId=...;https=0"
```

测试查询：

```bash
uv run usst-electricity poll-once
```

带通知测试：

```bash
uv run usst-electricity notify-test
uv run usst-electricity poll-once --notify
```

开始监控：

```bash
uv run usst-electricity watch
```

## 配置示例

默认配置文件位置：

| 系统 | 配置文件 |
| --- | --- |
| Windows | `%LOCALAPPDATA%\usst-electricity\config.yaml` |
| Linux / VPS | `~/.config/usst-electricity/config.yaml` |

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
uv run usst-electricity auth-import ".\main_request_header_raw.txt" --account main
uv run usst-electricity auth-import ".\roommate_request_header_raw.txt" --account roommate
```

监控所有启用账号：

```bash
uv run usst-electricity watch --all
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

WeLink 的 `x-hw-code` 和宿舍系统 Cookie 可能会过期；如果查询返回登录失效或 `Status=300`，重新抓包并执行 `auth-import`。
