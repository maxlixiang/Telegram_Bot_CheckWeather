# Telegram Weather Bot

## 项目简介
这是一个基于 Python 3.11、`python-telegram-bot`、SQLite 和 Docker 的 Telegram 天气机器人。
当前定位是单用户长期运行版本，适合部署到个人 VPS 上持续提供天气查询与每日自动推送服务。

## 当前已实现功能
- `/help`：查看帮助
- `/check`：查询当前已保存城市的天气
- `/add 城市名`：添加城市
- `/delete 城市名`：删除城市
- `/list`：查看当前城市列表
- `/start`：开启每日自动天气推送
- `/stop`：关闭每日自动天气推送
- `/settime HH:MM`：设置每日自动推送时间

## 本阶段优化
- `/add` 已升级为更友好的城市去重策略
- 现在会先做 geocoding，再按稳定的标准地点信息去重
- 像 `北京`、`beijing`、`Beijing`、`北京市` 这类常见别名，若解析到同一地点，会被识别为同一城市
- `cities` 表会兼容扩展并保存标准地点信息，旧数据无需删库重建
- `/check` 与自动推送已升级为更清晰的纯文本天气消息排版

## 环境变量说明
项目运行依赖 `.env` 文件。可以先复制 `.env.example` 再修改：

```bash
cp .env.example .env
```

需要填写的环境变量：

- `TELEGRAM_BOT_TOKEN`：Telegram BotFather 提供的机器人 token
- `TELEGRAM_USER_ID`：当前机器人唯一允许使用者的 Telegram 数字 user id
- `DEFAULT_TIMEZONE`：默认时区，例如 `Asia/Shanghai`
- `WEATHER_API_KEY`：当前阶段保留但未实际使用，可先保留占位值

## 命令说明
- `/help`：查看帮助
- `/add 城市名`：添加城市到 SQLite
- `/delete 城市名`：删除已保存城市
- `/list`：查看当前已保存城市列表，优先显示标准地点名
- `/check`：查询当前已保存城市的天气
- `/start`：开启每日自动天气推送
- `/stop`：关闭每日自动天气推送
- `/settime HH:MM`：设置每日自动天气推送时间，例如 `/settime 08:30`

## 自动推送时间说明
- 默认推送时间是 `08:00`
- 时间格式必须是 24 小时制 `HH:MM`
- 合法示例：`08:30`、`21:05`
- 非法示例：`8:30`、`25:00`、`08-30`、`0830`
- 如果当前已开启自动推送，执行 `/settime HH:MM` 后会立即按新时间生效
- 如果当前未开启自动推送，执行 `/settime HH:MM` 只会保存时间，待后续执行 `/start` 后生效
- 程序重启后，如果自动推送处于开启状态，会按已保存时间自动恢复任务

## 本地运行方式
1. 安装 Python 3.11
2. 创建并激活虚拟环境
3. 安装依赖
4. 创建 `.env`
5. 启动程序

示例：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.main
```

Windows PowerShell 示例：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m app.main
```

## Docker 本地运行方式
```bash
cp .env.example .env
docker compose up -d --build
docker compose logs -f
```

## VPS 部署步骤
```bash
git clone <your-repo-url>
cd telegram-weather-bot
cp .env.example .env
nano .env
docker compose up -d --build
docker compose logs -f
```

## 数据持久化说明
- SQLite 数据库文件位于 `data/weather.db`
- `docker-compose.yml` 已将宿主机的 `./data` 挂载到容器内 `/app/data`
- 即使容器重建，只要宿主机 `data/` 目录还在，城市列表、自动推送开关状态和推送时间都会保留
- `data/weather.db` 不应提交到 GitHub，也不会进入 Docker 镜像构建上下文

## 排错建议
1. 先看日志：`docker compose logs -f`
2. 检查 `.env` 是否存在且内容正确
3. 检查 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_USER_ID` 是否填写正确
4. 确认 VPS 可以正常访问外网
5. 确认 `data/` 目录挂载正常，程序有权限写入 SQLite 文件
