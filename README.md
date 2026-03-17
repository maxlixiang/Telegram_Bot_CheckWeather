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
1. 创建 `.env`
2. 填写环境变量
3. 构建并启动容器
4. 查看日志确认启动成功

```bash
cp .env.example .env
docker compose up -d --build
docker compose logs -f
```

## VPS 部署步骤
从零部署到 VPS 的最短路径如下：

1. 准备一台安装了 Docker 和 Docker Compose 的 Linux VPS
2. 克隆仓库到服务器
3. 进入项目目录
4. 复制 `.env.example` 为 `.env`
5. 编辑 `.env`，填写 `TELEGRAM_BOT_TOKEN`、`TELEGRAM_USER_ID`、`DEFAULT_TIMEZONE`
6. 执行构建并后台启动
7. 查看日志确认 bot 已正常启动

示例命令：

```bash
git clone <your-repo-url>
cd telegram-weather-bot
cp .env.example .env
nano .env
docker compose up -d --build
docker compose logs -f
```

## 命令说明
- `/help`：查看帮助
- `/add 城市名`：添加城市到 SQLite
- `/delete 城市名`：删除已保存城市
- `/list`：查看当前已保存城市列表
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

## 常见运维命令
启动或更新后后台运行：

```bash
docker compose up -d --build
```

停止服务：

```bash
docker compose down
```

重启容器：

```bash
docker compose restart
```

查看运行状态：

```bash
docker compose ps
```

查看日志：

```bash
docker compose logs -f
```

## 日志查看方式
推荐优先使用：

```bash
docker compose logs -f
```

它可以帮助你确认：
- 程序是否成功启动
- `.env` 是否读取正确
- 是否存在 Telegram 或天气服务请求错误
- 自动推送任务是否在启动时恢复

## 更新部署方式
如果你更新了代码，推荐使用下面的方式重新部署：

```bash
git pull
docker compose down
docker compose up -d --build
```

说明：
如果你修改了 `Dockerfile`、`docker-compose.yml`、`.env`、`requirements.txt` 或镜像内代码，单纯执行 `docker compose restart` 通常不会完整反映这些变更。

## 数据持久化说明
- SQLite 数据库文件位于 `data/weather.db`
- `docker-compose.yml` 已将宿主机的 `./data` 挂载到容器内 `/app/data`
- 即使容器重建，只要宿主机 `data/` 目录还在，城市列表、自动推送开关状态和推送时间都会保留
- `data/weather.db` 不应提交到 GitHub，也不会进入 Docker 镜像构建上下文

## 安全提醒
- 不要提交 `.env`
- 不要在 README、截图或日志中泄露 `TELEGRAM_BOT_TOKEN`
- 不要把真实的 `TELEGRAM_USER_ID`、token 或服务器地址公开提交
- 如果 token 泄露，请立即去 BotFather 重新生成

## 排错建议
如果部署后机器人没有正常工作，建议按这个顺序检查：

1. 先看日志：`docker compose logs -f`
2. 检查 `.env` 是否存在且内容正确
3. 检查 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_USER_ID` 是否填写正确
4. 确认 VPS 可以正常访问外网
5. 确认 `data/` 目录挂载正常，程序有权限写入 SQLite 文件

## 仓库说明
适合提交到 GitHub 的内容主要是源码、Docker 配置和文档。
不应提交的内容包括：
- `.env`
- `data/weather.db`
- 本地虚拟环境目录
- Python 缓存文件
- 本地编辑器配置目录
