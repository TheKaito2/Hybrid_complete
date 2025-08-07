#!/usr/bin/env python3
"""
SIMPLE HYBRID LAUNCHER FOR WINDOWS
No Unicode characters, maximum compatibility
"""

import os
import sys
import subprocess
import time
import signal
import json
from pathlib import Path

# Global process references
web_process = None
pyqt_process = None

def load_config():
    """Load configuration from hybrid_config.json"""
    config_file = Path('hybrid_config.json')
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def cleanup(signum=None, frame=None):
    """Clean up processes on exit"""
    global web_process, pyqt_process
    
    print("\n" + "="*60)
    print("Shutting down Hybrid System...")
    print("="*60)
    
    if pyqt_process:
        print("Stopping PyQt scanner...")
        try:
            pyqt_process.terminate()
            pyqt_process.wait(timeout=5)
            print("PyQt scanner stopped")
        except:
            try:
                pyqt_process.kill()
            except:
                pass
    
    if web_process:
        print("Stopping web server...")
        try:
            web_process.terminate()
            web_process.wait(timeout=5)
            print("Web server stopped")
        except:
            try:
                web_process.kill()
            except:
                pass
    
    print("\nGoodbye!")
    sys.exit(0)

def start_web_server(web_dir):
    """Start the web server"""
    global web_process
    
    print(f"Starting web server in: {web_dir}")
    
    # Save current directory
    original_dir = os.getcwd()
    
    try:
        # Change to web directory
        os.chdir(web_dir)
        
        # Start the web server
        web_process = subprocess.Popen(
            [sys.executable, "main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        print(f"Web server started (PID: {web_process.pid})")
        
        # Wait a bit for server to start
        print("Waiting for web server to initialize...")
        time.sleep(5)
        
        return web_process
        
    except Exception as e:
        print(f"ERROR: Failed to start web server: {e}")
        return None
    finally:
        # Return to original directory
        os.chdir(original_dir)

def start_pyqt_scanner(pyqt_dir):
    """Start the PyQt scanner"""
    global pyqt_process
    
    print(f"Starting PyQt scanner in: {pyqt_dir}")
    
    # Save current directory
    original_dir = os.getcwd()
    
    try:
        # Change to PyQt directory
        os.chdir(pyqt_dir)
        
        # Start the PyQt scanner
        pyqt_process = subprocess.Popen(
            [sys.executable, "main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        print(f"PyQt scanner started (PID: {pyqt_process.pid})")
        
        return pyqt_process
        
    except Exception as e:
        print(f"ERROR: Failed to start PyQt scanner: {e}")
        return None
    finally:
        # Return to original directory
        os.chdir(original_dir)

def monitor_output(process, name):
    """Monitor and print process output"""
    try:
        while process and process.poll() is None:
            line = process.stdout.readline()
            if line:
                print(f"[{name}] {line.strip()}")
    except:
        pass

def main():
    """Main launcher function"""
    
    # Clear screen
    os.system('cls' if os.name == 'nt' else 'clear')
    
    print("="*60)
    print("HYBRID SMART CHECKOUT SYSTEM LAUNCHER")
    print("="*60)
    print()
    
    # Setup signal handler
    signal.signal(signal.SIGINT, cleanup)
    
    # Load configuration
    print("Loading configuration...")
    config = load_config()
    
    if not config:
        print("ERROR: Configuration file 'hybrid_config.json' not found!")
        print("Please run 'find_and_setup.py' first to configure directories.")
        input("\nPress Enter to exit...")
        return
    
    web_dir = config.get('web_dir')
    pyqt_dir = config.get('pyqt_dir')
    
    # Convert to Path objects for better handling
    web_dir = Path(web_dir)
    pyqt_dir = Path(pyqt_dir)
    
    # Verify directories exist
    if not web_dir.exists():
        print(f"ERROR: Web directory not found: {web_dir}")
        input("\nPress Enter to exit...")
        return
    
    if not pyqt_dir.exists():
        print(f"ERROR: PyQt directory not found: {pyqt_dir}")
        input("\nPress Enter to exit...")
        return
    
    print(f"Web System:  {web_dir}")
    print(f"PyQt System: {pyqt_dir}")
    print()
    print("-"*60)
    
    # Start web server
    print("\nSTEP 1: Starting Web Server")
    print("-"*60)
    web_proc = start_web_server(web_dir)
    
    if not web_proc:
        print("ERROR: Failed to start web server.")
        input("\nPress Enter to exit...")
        return
    
    print("SUCCESS: Web server is running!")
    print()
    
    # Start PyQt scanner
    print("STEP 2: Starting PyQt Scanner")
    print("-"*60)
    pyqt_proc = start_pyqt_scanner(pyqt_dir)
    
    if not pyqt_proc:
        print("ERROR: Failed to start PyQt scanner.")
        print("Web server will continue running.")
        print("You can try starting PyQt manually.")
    else:
        print("SUCCESS: PyQt scanner is running!")
    
    # Show access information
    print()
    print("="*60)
    print("HYBRID SYSTEM IS RUNNING!")
    print("="*60)
    print()
    print("Access Points:")
    print("  Cart:      http://localhost:8000/cart")
    print("  Inventory: http://localhost:8000/")
    print("  Analytics: http://localhost:8000/admin")
    print()
    print("Press Ctrl+C to stop both systems")
    print("="*60)
    print()
    
    # Monitor processes
    try:
        if pyqt_proc:
            # Wait for PyQt to close
            pyqt_proc.wait()
            print("\nPyQt scanner has closed.")
            
        if web_proc:
            print("Web server is still running.")
            print("Press Ctrl+C to stop it.")
            web_proc.wait()
            
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()

if __name__ == "__main__":
    main()