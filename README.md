# Telegram Weather Bot

## 项目简介
这是一个基于 Python 3.11 和 `python-telegram-bot` 的 Telegram 天气机器人项目。
目标是在后续阶段支持天气查询、城市管理和自动天气推送。

## 当前阶段已完成内容
- 完成项目目录骨架初始化
- 完成环境变量配置读取
- 完成 bot 最小启动流程
- 启动时自动准备 `data/` 目录和 SQLite 数据库
- 已支持 `/help`、`/check`、`/add`、`/delete`、`/list`
- 城市列表已接入 SQLite 持久化存储
- `/check` 现在从数据库读取城市列表并返回当前天气和未来 7 天概览
- 对天气 API 请求失败增加基础错误处理
- 当前机器人仅服务单用户

## 当前阶段未实现
当前阶段尚未实现：
- 自动天气推送
- `/start`、`/stop`
- 多用户系统和复杂权限模型

## 第三阶段说明
- 当前只允许配置的 `TELEGRAM_USER_ID` 使用 `/check`、`/add`、`/delete`、`/list`
- 未授权用户调用受限命令时，会收到：`无权限使用该命令。`
- 城市名会做最小规范化后再入库：去掉首尾空格，并将连续空白压缩为单个空格
- SQLite 数据库存储在 `data/weather.db`
- 城市列表按添加顺序返回
- 天气数据继续使用 Open-Meteo API

## 项目目录结构
```text
.
|-- app/
|   |-- __init__.py
|   |-- main.py
|   |-- config.py
|   |-- bot/
|   |   |-- __init__.py
|   |   `-- handlers.py
|   |-- services/
|   |   |-- __init__.py
|   |   `-- weather_service.py
|   |-- db/
|   |   |-- __init__.py
|   |   `-- database.py
|   `-- utils/
|       `-- __init__.py
|-- data/
|   `-- .gitkeep
|-- tests/
|   `-- .gitkeep
|-- .env.example
|-- .gitignore
|-- Dockerfile
|-- docker-compose.yml
|-- README.md
`-- requirements.txt
```

## 环境变量说明
- `TELEGRAM_BOT_TOKEN`: 必填，Telegram 机器人令牌
- `TELEGRAM_USER_ID`: 必填，当前唯一允许操作机器人的 Telegram 用户 ID
- `WEATHER_API_KEY`: 当前阶段保留但未实际使用，后续如切换天气服务可接入
- `DEFAULT_TIMEZONE`: 默认时区

## 命令说明
- `/help`: 查看帮助
- `/add 城市名`: 添加城市到 SQLite
- `/delete 城市名`: 删除已保存城市
- `/list`: 查看当前已保存城市列表
- `/check`: 查询当前已保存城市的天气

## 本地运行方式
1. 使用 Python 3.11 创建虚拟环境。
2. 安装依赖：`pip install -r requirements.txt`
3. 复制环境变量模板：将 `.env.example` 另存为 `.env`
4. 在 `.env` 中填写 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_USER_ID`
5. 启动项目：`python -m app.main`
6. 在 Telegram 中先发送 `/add 北京`
7. 再发送 `/list` 和 `/check` 验证 SQLite 和天气查询链路

## Docker 运行方式
1. 将 `.env.example` 另存为 `.env`
2. 填写环境变量
3. 构建并启动：`docker compose up --build`
4. 在 Telegram 中使用 `/add`、`/list`、`/check`

## 后续开发计划
- 增加自动天气推送
- 引入 `/start`、`/stop`
- 扩展到多用户场景
