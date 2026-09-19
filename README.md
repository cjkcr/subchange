# Subchange

一个轻量的 Django 字幕转换与双语翻译服务，支持 SRT、ASS、SSA、VTT 和 SUB。

[在线使用](https://mail.cenship.xyz) · [English](#english) · [中文说明](#中文说明)

## 中文说明

### 功能

- 在 SRT、ASS、SSA、VTT、SUB 格式之间转换字幕。
- 将字幕翻译为中文、英文、西班牙语或法语。
- 输出“译文 + 原文”的双语字幕。
- 保留常见时间轴、方括号内容和斜体字幕结构。
- 上传和生成文件均使用临时文件，响应完成后自动删除。
- 单个上传文件最大 5 MB。

### 在线服务

直接访问：<https://mail.cenship.xyz>

生产环境采用以下结构：

```text
Browser → HTTPS/Nginx → Gunicorn → Django
                           ↓
                    Google translation endpoint
```

Gunicorn 仅监听 `127.0.0.1:8000`，公网流量必须经过 Nginx 和 HTTPS。

### 本地运行

需要 Python 3.10 或更高版本。

```bash
git clone https://github.com/cjkcr/subchange.git
cd subchange

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export DJANGO_SECRET_KEY='local-development-only-change-me'
export DJANGO_DEBUG=true
export DJANGO_DB_PATH="$PWD/subtitle_converter/db.sqlite3"
export DJANGO_STATIC_ROOT="$PWD/subtitle_converter/staticfiles"

cd subtitle_converter
python manage.py migrate
python manage.py runserver
```

打开 <http://127.0.0.1:8000/converter/>。

### 环境变量

| 变量 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `DJANGO_SECRET_KEY` | 是 | 无 | Django 密钥，生产环境必须使用随机值 |
| `DJANGO_DEBUG` | 否 | `false` | 本地开发时可设为 `true` |
| `DJANGO_DB_PATH` | 否 | `/var/lib/subchange/db.sqlite3` | SQLite 数据库路径 |
| `DJANGO_STATIC_ROOT` | 否 | `/var/lib/subchange/static` | `collectstatic` 输出目录 |

### 生产部署

当前线上环境使用：

- Django 5.2 LTS
- Gunicorn `gthread` worker
- systemd 服务：`subchange.service`
- Nginx TLS 终止和反向代理
- 独立系统账号 `subchange`
- `/etc/subchange.env` 保存生产环境变量
- `/opt/subchange/app` 保存部署代码
- `/opt/subchange/venv` 保存隔离 Python 环境
- `/var/lib/subchange` 保存数据库和静态文件

常用运维命令：

```bash
sudo systemctl status subchange
sudo systemctl restart subchange
sudo journalctl -u subchange -f
sudo nginx -t
```

生产环境检查：

```bash
set -a
source /etc/subchange.env
set +a
cd /opt/subchange/app/subtitle_converter
/opt/subchange/venv/bin/python manage.py check --deploy
```

### 项目结构

```text
subchange/
├── requirements.txt
├── README.md
└── subtitle_converter/
    ├── manage.py
    ├── converter/
    │   ├── templates/converter/upload.html
    │   ├── urls.py
    │   └── views.py
    └── subtitle_converter/
        ├── settings.py
        ├── urls.py
        └── wsgi.py
```

### 注意事项

- 翻译功能依赖外部 Google 翻译端点，其可用性和结果质量不由本项目保证。
- 请勿把 `DJANGO_SECRET_KEY`、服务器证书或 `/etc/subchange.env` 提交到 Git。
- 本项目不永久保存用户上传的字幕，但生产运营者仍应配置合理的日志、访问控制和备份策略。

## English

Subchange is a small Django web service for converting and translating subtitle files.

### Features

- Convert between SRT, ASS, SSA, VTT, and SUB.
- Translate subtitles into Chinese, English, Spanish, or French.
- Generate bilingual output containing the translation and original text.
- Preserve common timing, bracketed text, and italic subtitle structures.
- Remove temporary upload and output files after each response.
- Enforce a 5 MB upload limit.

### Live service

Open <https://mail.cenship.xyz>.

### Local development

Python 3.10 or newer is required.

```bash
git clone https://github.com/cjkcr/subchange.git
cd subchange

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export DJANGO_SECRET_KEY='local-development-only-change-me'
export DJANGO_DEBUG=true
export DJANGO_DB_PATH="$PWD/subtitle_converter/db.sqlite3"
export DJANGO_STATIC_ROOT="$PWD/subtitle_converter/staticfiles"

cd subtitle_converter
python manage.py migrate
python manage.py runserver
```

Then open <http://127.0.0.1:8000/converter/>.

For production, keep debug mode disabled, use a random secret key, run the application behind Gunicorn and Nginx, and execute `python manage.py check --deploy` before release.

## Contributing

Issues and pull requests are welcome.
