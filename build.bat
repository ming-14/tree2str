@echo off
rem ============================================================
rem  tree2str 打包脚本（Win7 兼容）
rem  使用 WinPython 3.8.10 + PyInstaller 5.13.2 打包为单文件 exe
rem ============================================================
setlocal
set "PY=C:\Users\rikka\Desktop\WPy64-38100\python-3.8.10.amd64\python.exe"
cd /d "%~dp0"

"%PY%" -m PyInstaller run.py ^
  --name tree2str ^
  --onefile ^
  --console ^
  --paths src ^
  --add-data "src/data;data" ^
  --clean --noconfirm

echo.
echo ============================================================
echo  Done. Output: %~dp0dist\tree2str.exe
echo ============================================================
pause
