@echo off
chcp 65001 > nul
echo 正在安装新闻聚合系统所需依赖...
echo ==============================

echo 正在安装所有依赖包...
pip install -r requirements.txt

echo.
echo 安装完成！
echo 如果没有错误提示，则表示所有依赖已成功安装。
echo.
pause