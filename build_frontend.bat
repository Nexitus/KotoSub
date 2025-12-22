@echo off
echo Setting Node.js Path...
set PATH=%PATH%;C:\Program Files\nodejs
echo Building Frontend...
cd frontend
call npm install
call npm run build
echo Build Complete.
pause
