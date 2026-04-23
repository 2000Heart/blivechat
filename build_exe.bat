@echo off
setlocal
cd /d "%~dp0"

if not exist "blivedm\blivedm\__init__.py" (
  echo 缺少 blivedm 子模块，正在初始化...
  git submodule update --init --recursive || exit /b 1
)

if not exist "frontend\dist\index.html" (
  echo 缺少前端构建产物，正在编译 frontend...
  pushd frontend
  call npm install
  if errorlevel 1 exit /b 1
  call npm run build
  if errorlevel 1 exit /b 1
  popd
)

python -m pip install -r requirements-windows-build.txt
if errorlevel 1 exit /b 1

python -m PyInstaller -y blivechat.spec
if errorlevel 1 exit /b 1

echo.
echo 完成: dist\blivechat\blivechat.exe
echo 压缩包: dist\blivechat.zip
endlocal
