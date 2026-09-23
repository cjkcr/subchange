# Subchange

<div align="left">
  <strong>English</strong> · <a href="./README_CN.md">简体中文</a>
</div>

Subchange is a lightweight Django web service for converting and translating subtitle files.

[Use the live service](https://mail.cenship.xyz)

## Features

- Convert between SRT, ASS, SSA, and VTT.
- Translate subtitles into Chinese, English, Spanish, or French.
- Choose translation-only output or bilingual output containing both the translation and original text.
- Preserve common timing, bracketed text, and italic subtitle structures.
- Remove temporary upload and output files after each response.
- Enforce a 5 MB upload limit.
- Switch the website interface between English and Simplified Chinese from the top-left button; the choice is remembered in the browser.

## Live service

Open <https://mail.cenship.xyz>.

The production request path is:

```text
Browser → HTTPS/Nginx → Gunicorn → Django
                           ↓
                    Google translation endpoint
```

Gunicorn listens only on `127.0.0.1:8000`; public traffic is served through Nginx over HTTPS.

## Local development

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

Open <http://127.0.0.1:8000/converter/>.

## Environment variables

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `DJANGO_SECRET_KEY` | Yes | None | Django secret key; use a random value in production |
| `DJANGO_DEBUG` | No | `false` | Set to `true` only for local development |
| `DJANGO_DB_PATH` | No | `/var/lib/subchange/db.sqlite3` | SQLite database path |
| `DJANGO_STATIC_ROOT` | No | `/var/lib/subchange/static` | Output directory for `collectstatic` |

## Production deployment

The current production deployment uses:

- Django 5.2 LTS
- Gunicorn with `gthread` workers
- A systemd service named `subchange.service`
- Nginx for TLS termination and reverse proxying
- A dedicated `subchange` system account
- `/etc/subchange.env` for production environment variables
- `/opt/subchange/app` for deployed application code
- `/opt/subchange/venv` for the isolated Python environment
- `/var/lib/subchange` for the database and static files

Common operations:

```bash
sudo systemctl status subchange
sudo systemctl restart subchange
sudo journalctl -u subchange -f
sudo nginx -t
```

Run Django's deployment checks before a release:

```bash
set -a
source /etc/subchange.env
set +a
cd /opt/subchange/app/subtitle_converter
/opt/subchange/venv/bin/python manage.py check --deploy
```

## Project structure

```text
subchange/
├── requirements.txt
├── README.md
├── README_CN.md
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

## Notes

- Translation depends on an external Google Translate endpoint; its availability and output quality are outside this project's control.
- Never commit `DJANGO_SECRET_KEY`, server certificates, or `/etc/subchange.env` to Git.
- Uploaded subtitles are not stored permanently, but production operators should still configure appropriate logging, access controls, and backups.

## Contributing

Issues and pull requests are welcome.
