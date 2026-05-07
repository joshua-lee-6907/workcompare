@echo off
chcp 65001 >nul
echo [INFO] 开始修复 matplotlib 中文方框问题...

python fix_matplotlib_chinese.py
if errorlevel 1 (
  echo [ERROR] 执行失败，请确认已安装 Python 和 matplotlib。
  pause
  exit /b 1
)

echo.
echo [DONE] 修复完成。请重启你的 Python/IDE 后再运行绘图脚本。
pause
