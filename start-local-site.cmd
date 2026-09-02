@echo off
setlocal EnableExtensions
title Refraction LAB - Local Site
cd /d "%~dp0"

set "CODEX_NODE_DIR=C:\Users\drose\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin"
set "CODEX_PNPM=C:\Users\drose\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\fallback\pnpm.cmd"
set "PNPM_COMMAND="

if exist "%CODEX_NODE_DIR%\node.exe" (
  set "PATH=%CODEX_NODE_DIR%;%PATH%"
) else (
  where node.exe >nul 2>&1
  if errorlevel 1 goto missing_node
)

if exist "%CODEX_PNPM%" (
  set "PNPM_COMMAND=%CODEX_PNPM%"
) else (
  where pnpm.cmd >nul 2>&1
  if errorlevel 1 goto missing_pnpm
  set "PNPM_COMMAND=pnpm.cmd"
)

echo.
echo Refraction LAB local launcher
echo Project: %CD%
echo.

if not exist "node_modules\.modules.yaml" (
  echo Installing project dependencies...
  call "%PNPM_COMMAND%" install
  if errorlevel 1 goto install_failed
  echo.
)

echo Starting the site at http://localhost:3000
echo Keep this window open. Press Ctrl+C to stop the site.
echo.

if /I not "%REFRACTION_NO_OPEN%"=="1" (
  start "" /b powershell.exe -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 4; Start-Process 'http://localhost:3000'"
)
call "%PNPM_COMMAND%" dev
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo The local server stopped with error code %EXIT_CODE%.
  pause
)
exit /b %EXIT_CODE%

:missing_node
echo.
echo Node.js was not found.
echo Install Node.js 22.13 or newer, then run this file again.
pause
exit /b 1

:missing_pnpm
echo.
echo pnpm was not found.
echo Install pnpm, then run this file again.
pause
exit /b 1

:install_failed
echo.
echo Dependency installation failed. Check your internet connection and try again.
pause
exit /b 1
