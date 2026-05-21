@echo off
chcp 65001 >nul
echo ==========================================
echo    🍜 私人规划执行助理 - Inspire UI
echo ==========================================
echo.

REM 检查虚拟环境
if exist "..\.venv\Scripts\activate.bat" (
    echo [✓] 找到虚拟环境
    call "..\.venv\Scripts\activate.bat"
) else (
    echo [!] 未找到虚拟环境，尝试使用系统 Python
)

echo.
echo [+] 启动 Inspire UI...
echo [+] 请稍候...
echo.

REM 启动 Streamlit
streamlit run streamlit_app.py --server.port 8501 --server.headless true

REM 如果启动失败，暂停显示错误
if %errorlevel% neq 0 (
    echo.
    echo [!] 启动失败，错误代码: %errorlevel%
    pause
)

exit /b %errorlevel%