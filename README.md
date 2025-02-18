# subchange

<!-- 中英文切换按钮 -->
<div align="center">
  <a href="#english">English</a> | <a href="#chinese">中文</a>
</div>

## English
This is a website using Django that can convert subtitle files between SRT, ASS, SSA, and VTT formats. On February 14, 2025, the translation function was updated to generate dual subtitles.

### How to Use
1. Clone the repository:
    ```bash
    git clone https://github.com/yourusername/subchange.git
    cd subchange
    ```
2. Create and activate a virtual environment:
    ```bash
    python -m venv env
    source env/bin/activate  # For Windows: use `venv\Scripts\activate`
    ```
3. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
4. Run database migrations:
    ```bash
    python manage.py migrate
    ```
5. Start the development server:
    ```bash
    python manage.py runserver
    ```
6. Open `http://127.0.0.1:8000/converter/` in your browser to use the subtitle format converter.

## 中文
该项目是一个基于 Django 的网站应用，可以在 SRT、ASS、SSA 和 VTT 格式之间转换字幕文件。2025年2月14日更新翻译功能，生成双字幕。

### 使用方法
1. 克隆项目仓库：
    ```bash
    git clone https://github.com/yourusername/subchange.git
    cd subchange
    ```
2. 创建并激活虚拟环境：
    ```bash
    python -m venv env
    source env/bin/activate  # 对于 Windows 系统，使用 `venv\Scripts\activate`
    ```
3. 安装依赖：
    ```bash
    pip install -r requirements.txt
    ```
4. 运行数据库迁移：
    ```bash
    python manage.py migrate
    ```
5. 启动开发服务器：
    ```bash
    python manage.py runserver
    ```
6. 在浏览器中打开 `http://127.0.0.1:8000/converter/`，开始使用字幕格式转换工具。

## Contributing
If you would like to contribute, please fork the repository and submit a pull request.

## License
This project is licensed under the MIT License. For details, see the LICENSE file.