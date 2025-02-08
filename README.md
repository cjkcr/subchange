# subchange
This is a website using Django that can convert subtitle files between SRT, ASS, SSA, and VTT formats.

## 项目说明
该项目是一个基于 Django 的网站应用，可以在 SRT、ASS、SSA和VTT格式之间转换字幕文件。

## 使用方法
1. 克隆项目仓库：
    ```bash
    git clone https://github.com/yourusername/subchange.git
    cd subchange
    ```

2. 创建并激活虚拟环境：
    ```bash
    python -m venv venv
    source venv/bin/activate  # 对于 Windows 系统，使用 `venv\Scripts\activate`
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

6. 在浏览器中打开 `http://127.0.0.1:8000/converter/`，开始使用网站进行字幕格式转换。

## 贡献
如果你想为该项目做出贡献，请 fork 该仓库并提交 pull request。

## 许可证
该项目使用 MIT 许可证。详细信息请参阅 LICENSE 文件。
