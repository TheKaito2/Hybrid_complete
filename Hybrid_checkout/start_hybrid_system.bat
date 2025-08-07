@echo off
echo ===============================================
echo HYBRID SMART CHECKOUT SYSTEM - WINDOWS LAUNCHER
echo ===============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7+ and try again
    pause
    exit /b 1
)

REM Start web server in new window
echo Starting Web Server...
cd smart-checkout-optimized 2>nul
if errorlevel 1 (
    echo ERROR: Cannot find smart-checkout-optimized directory
    echo Please run this script from the parent directory
    pause
    exit /b 1
)

start "Web Server - Smart Checkout" cmd /k python main.py
cd ..

REM Wait for server to start
echo Waiting for web server to start...
timeout /t 5 /nobreak >nul

REM Start PyQt scanner
echo Starting PyQt Scanner...
cd Hello\self-checkout-system 2>nul
if errorlevel 1 (
    cd self-checkout-system 2>nul
    if errorlevel 1 (
        echo ERROR: Cannot find PyQt scanner directory
        echo Expected: Hello\self-checkout-system or self-checkout-system
        pause
        exit /b 1
    )
)

echo.
echo ===============================================
echo SYSTEM STARTED SUCCESSFULLY!
echo ===============================================
echo.
echo Web Interface: http://localhost:8000/cart
echo.
echo Starting PyQt Scanner...
python main.py

echo.
echo PyQt Scanner closed. Press any key to stop web server...
pause >nul

REM Kill web server
taskkill /FI "WINDOWTITLE eq Web Server - Smart Checkout*" /F >nul 2>&1

echo.
echo System stopped.
pause