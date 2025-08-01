@echo off
echo ========================================
echo DbRheo项目依赖安装脚本
echo ========================================
echo.

echo 正在安装核心依赖...
echo.

REM 基础工具
pip install rich>=13.9.0
pip install click>=8.1.7
pip install pydantic>=2.10.0
pip install pyyaml>=6.0.2

REM Web框架
pip install fastapi>=0.115.0
pip install uvicorn[standard]>=0.32.0
pip install websockets>=13.1

REM 数据库相关
pip install sqlalchemy[asyncio]>=2.0.36
pip install aiosqlite>=0.20.0
pip install asyncpg>=0.30.0
pip install aiomysql>=0.2.0

REM AI服务
pip install google-generativeai>=0.8.3
pip install google-auth>=2.35.0
pip install google-auth-oauthlib>=1.2.1

REM 工具库
pip install httpx>=0.28.0
pip install aiofiles>=24.1.0
pip install python-multipart>=0.0.12

REM HTTP客户端相关
pip install aiohttp>=3.9.0
pip install aiohappyeyeballs>=2.4.0
pip install aiosignal>=1.3.0
pip install attrs>=23.0.0
pip install multidict>=6.0.0
pip install yarl>=1.9.0
pip install frozenlist>=1.4.0

REM 网络和解析相关
pip install beautifulsoup4>=4.12.0
pip install soupsieve>=2.5.0
pip install requests>=2.31.0
pip install urllib3>=2.0.0
pip install certifi>=2023.0.0
pip install charset-normalizer>=3.3.0
pip install idna>=3.4.0

REM 开发工具（可选）
pip install pytest>=8.3.0
pip install pytest-asyncio>=0.24.0
pip install black>=24.10.0
pip install mypy>=1.13.0
pip install ruff>=0.8.0

REM 监控遥测（可选）
pip install opentelemetry-api>=1.28.0
pip install opentelemetry-sdk>=1.28.0
pip install opentelemetry-exporter-otlp>=1.28.0

echo.
echo ========================================
echo 依赖安装完成！
echo ========================================
echo.

echo 验证安装...
python -c "import rich; print('✅ rich 安装成功')"
python -c "import fastapi; print('✅ fastapi 安装成功')"
python -c "import sqlalchemy; print('✅ sqlalchemy 安装成功')"
python -c "import google.generativeai; print('✅ google-generativeai 安装成功')"
python -c "import aiohttp; print('✅ aiohttp 安装成功')"
python -c "import bs4; print('✅ beautifulsoup4 安装成功')"

echo.
echo 现在可以运行项目了！
pause
