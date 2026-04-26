# usst-e-fees

上海理工大学宿舍电费提醒工具。

它会定时查看宿舍照明电费和空调电费。余额低于你设置的金额时，会通过 Bark、Gotify、邮件或控制台提醒你。

> 经过测试，学校宿舍电费接口目前只能在校内网络访问。请在校园网、宿舍网络、校内服务器，或可以访问校内资源的 VPN 环境运行。

## 能做什么

- 查看当前宿舍电费和电量。
- 照明电费、空调电费可以分别设置提醒金额。
- 余额不足时自动提醒。
- 支持 Bark 手机推送。
- 支持多个账号。
- 会自动避免短时间内重复提醒。

## 安装

推荐使用 `uv`：

```bash
uv tool install usst-e-fees
```

安装后检查命令是否可用：

```bash
usst-e-fees --help
usst-e-fees version
```

如果是从源码安装：

```bash
uv tool install --editable .
```

## 第一次使用

### 1. 生成配置文件

```bash
usst-e-fees init-config
usst-e-fees where
```

`where` 会显示配置文件位置。Windows 常见位置是：

```text
%LOCALAPPDATA%\usst-e-fees\config.yaml
```

### 2. 配置提醒金额

打开配置文件，找到：

```yaml
thresholds:
  lighting_money: 20.0
  aircon_money: 20.0
```

含义：

- `lighting_money`：照明电费低于多少元时提醒。
- `aircon_money`：空调电费低于多少元时提醒。

### 3. 配置 Bark 推送

如果你使用 Bark，打开配置文件，填入你的 Bark key：

```yaml
notify:
  bark:
    enabled: true
    server: https://api.day.app
    key: 你的 Bark key
    group: USST E Fees
```

测试通知：

```bash
usst-e-fees notify-test
```

### 4. 导入登录信息

工具需要从已登录的 WeLink/宿舍电费页面请求中导入登录信息。

用 Loon 抓包后，建议导入两条请求的 `request_header_raw.txt`：

- 宿舍电费查询请求。
- WeLink 授权刷新请求，路径里通常包含 `ssoauth/v1/code`。

导入示例：

```bash
usst-e-fees auth-import "D:\path\to\dorm_request_header_raw.txt"
usst-e-fees auth-import "D:\path\to\welink_sso_request_header_raw.txt"
```

导入后测试刷新登录信息：

```bash
usst-e-fees auth-refresh
```

如果以后提示登录失效，重新抓包并再次执行上面的 `auth-import`。

## 查询和监控

### 查询一次

```bash
usst-e-fees poll-once
```

这个命令只显示余额，不会发送低余额提醒。

### 查询一次并提醒

```bash
usst-e-fees poll-once --notify
```

如果余额低于阈值，会发送提醒。

### 持续监控

```bash
usst-e-fees watch
```

`watch` 会自动发送提醒，不需要加 `--notify`。

### 监控所有账号

```bash
usst-e-fees watch --all
```

`watch --all` 也会自动发送提醒。它会监控配置文件中所有 `enabled: true` 的账号。

## 防重复提醒

默认情况下，同一账号的同一种电费 6 小时内最多提醒一次。

例如空调电费一直低于阈值，工具不会每次检查都推送；等过了冷却时间才会再次提醒。余额恢复到阈值以上后，低余额状态会被清除。

## 多账号

可以在配置文件里添加多个账号：

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

给不同账号导入登录信息：

```bash
usst-e-fees auth-import "D:\path\to\main_request_header_raw.txt" --account main
usst-e-fees auth-import "D:\path\to\roommate_request_header_raw.txt" --account roommate
```

监控所有账号：

```bash
usst-e-fees watch --all
```

## 常见问题

### `watch --all` 是否自带通知？

是。`watch` 和 `watch --all` 都会在低于阈值时自动通知。

### `poll-once` 会不会通知？

默认不会。要通知请使用：

```bash
usst-e-fees poll-once --notify
```

### 为什么校外运行失败？

当前学校接口经测试仅限校内网络访问。校外运行请先确认当前机器可以访问校内宿舍管理系统。

### 为什么过一段时间提示登录失效？

登录信息会过期。重新用 Loon 抓包并导入请求头即可。

## 开发和发布

源码仓库：[Nitmi/usst-e-fees](https://github.com/Nitmi/usst-e-fees)

维护者发布 GitHub Release 后，会由 GitHub Actions 自动构建并发布到 PyPI。首次发布前，需要先在 PyPI 为 `Nitmi/usst-e-fees` 配置 Trusted Publisher。

## 联系方式

问题反馈：a.oxidizing172@aleeas.com
