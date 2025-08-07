#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import socket
import webbrowser
import threading
from pathlib import Path

def check_port(port=8000):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('localhost', port))
    sock.close()
    return result != 0

def open_browser_delayed():
    time.sleep(3)
    webbrowser.open('http://localhost:8000')

def print_banner():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("\n" + "="*60)
    print("🛒 SMART CHECKOUT SYSTEM - OPTIMIZED VERSION")
    print("="*60)
    
    models_dir = Path("models")
    if not models_dir.exists():
        print("\n⚠️  Creating 'models' directory...")
        models_dir.mkdir(exist_ok=True)
        print("   Please add your YOLO models!")
    
    print("\n📍 Access Points:")
    print("   🏪 http://localhost:8000          - Inventory")
    print("   📸 http://localhost:8000/checkout - Scanner")
    print("   📊 http://localhost:8000/admin    - Analytics")
    
    print("\n✨ Features:")
    print("   🌓 Dark Mode Toggle")
    print("   💳 QR Code Payment")
    print("   📊 Best Sellers Ranking")
    
    print("\n" + "-"*60)
    print("Press Ctrl+C to stop the server")
    print("="*60 + "\n")

def main():
    print_banner()
    
    if not check_port(8000):
        print("❌ Port 8000 is already in use!")
        sys.exit(1)
    
    browser_thread = threading.Thread(target=open_browser_delayed)
    browser_thread.daemon = True
    browser_thread.start()
    
    print("🚀 Starting server...\n")
    
    try:
        subprocess.run([sys.executable, "main.py"])
    except KeyboardInterrupt:
        print("\n\n✅ Server stopped.")

if __name__ == "__main__":
    main()
