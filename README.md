# Telegram Weather Bot

## 项目简介
这是一个基于 Python 3.11 和 `python-telegram-bot` 的 Telegram 天气机器人项目。
目标是在后续阶段支持天气查询、城市管理和自动天气推送。

## 当前阶段已完成内容
- 完成项目目录骨架初始化
- 完成环境变量配置读取
- 完成 bot 最小启动流程
- 注册并实现 `/help` 占位命令
- 启动时自动准备 `data/` 目录
- 打通 `/check` 命令
- `/check` 当前固定查询北京、上海
- 返回当前天气和未来 7 天概览
- 对天气 API 请求失败增加基础错误处理

## 当前阶段未实现
当前阶段尚未实现：
- 城市管理
- 自动天气推送
- 数据库表设计与持久化逻辑
- `/add`、`/delete`、`/list`、`/start`、`/stop`

## 第二阶段说明
- 第二阶段只实现 `/check + 固定城市天气`
- 固定城市当前为：北京、上海
- 不引入数据库持久化，不实现城市管理
- 不实现自动推送
- 天气数据使用 Open-Meteo API
- 当前阶段继续保留 `WEATHER_API_KEY` 配置项，但尚未实际使用

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
- `TELEGRAM_USER_ID`: 当前阶段仅读取，后续将用于限制机器人服务对象
- `WEATHER_API_KEY`: 当前阶段保留但未实际使用，后续如切换天气服务可接入
- `DEFAULT_TIMEZONE`: 默认时区

## 本地运行方式
1. 使用 Python 3.11 创建虚拟环境。
2. 安装依赖：`pip install -r requirements.txt`
3. 复制环境变量模板：将 `.env.example` 另存为 `.env`
4. 在 `.env` 中填写至少 `TELEGRAM_BOT_TOKEN`
5. 启动项目：`python -m app.main`
6. 在 Telegram 中发送 `/check`，查看北京、上海的当前天气和未来 7 天概览

## Docker 运行方式
1. 将 `.env.example` 另存为 `.env`
2. 填写环境变量
3. 构建并启动：`docker compose up --build`
4. 在 Telegram 中发送 `/check`

## 后续开发计划
- 增加城市列表管理
- 增加自动天气推送
- 引入实际数据持久化
