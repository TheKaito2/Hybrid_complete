#!/bin/bash

echo "==============================================="
echo "HYBRID SMART CHECKOUT SYSTEM - LINUX/MAC LAUNCHER"
echo "==============================================="
echo ""

# Check Python
if ! command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
    echo "ERROR: Python is not installed or not in PATH"
    echo "Please install Python 3.7+ and try again"
    read -p "Press any key to continue..."
    exit 1
fi

# Determine which Python command to use
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
fi

# Start web server in new terminal/background
echo "Starting Web Server..."
if [ -d "smart-checkout-optimized" ]; then
    cd smart-checkout-optimized
else
    echo "ERROR: Cannot find smart-checkout-optimized directory"
    echo "Please run this script from the parent directory"
    read -p "Press any key to continue..."
    exit 1
fi

# Start web server in background and save its PID
echo "Starting web server in background..."
$PYTHON_CMD main.py &
WEB_SERVER_PID=$!
cd ..

# Wait for server to start
echo "Waiting for web server to start..."
sleep 5

# Start PyQt scanner
echo "Starting PyQt Scanner..."
if [ -d "Hello/self-checkout-system" ]; then
    cd Hello/self-checkout-system
elif [ -d "self-checkout-system" ]; then
    cd self-checkout-system
else
    echo "ERROR: Cannot find PyQt scanner directory"
    echo "Expected: Hello/self-checkout-system or self-checkout-system"
    read -p "Press any key to continue..."
    # Kill the web server before exiting
    kill $WEB_SERVER_PID 2>/dev/null
    exit 1
fi

echo ""
echo "==============================================="
echo "SYSTEM STARTED SUCCESSFULLY!"
echo "==============================================="
echo ""
echo "Web Interface: http://localhost:8000/cart"
echo ""
echo "Starting PyQt Scanner..."
$PYTHON_CMD main.py

echo ""
echo "PyQt Scanner closed. Stopping web server..."

# Kill web server
kill $WEB_SERVER_PID 2>/dev/null

echo ""
echo "System stopped."
read -p "Press any key to continue..."