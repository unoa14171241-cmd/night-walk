@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo === Git Status ===
git status

echo.
echo === Git Remote ===
git remote -v

pause
