#!/usr/bin/env python3
"""
DIRECTORY FINDER AND SETUP HELPER
This script will help you find your directories and set up the hybrid system
"""

import os
import sys
from pathlib import Path
import json

def find_all_directories():
    """Find all potential project directories"""
    print("\n🔍 Searching for project directories...\n")
    
    current_dir = Path.cwd()
    found_dirs = {
        'web': [],
        'pyqt': [],
        'other': []
    }
    
    # Search patterns for web system
    web_patterns = [
        'smart-checkout',
        'web-checkout',
        'checkout-optimized',
        'fastapi',
        'web'
    ]
    
    # Search patterns for PyQt system
    pyqt_patterns = [
        'self-checkout',
        'pyqt',
        'scanner',
        'qt-checkout',
        'Hello'
    ]
    
    # Search in current directory and one level deep
    for path in current_dir.rglob('*'):
        if path.is_dir() and not path.name.startswith('.') and not path.name.startswith('__'):
            path_str = str(path.relative_to(current_dir))
            
            # Skip common non-project directories
            skip_dirs = ['node_modules', 'venv', 'env', '.git', '__pycache__', 'build', 'dist']
            if any(skip in path_str for skip in skip_dirs):
                continue
            
            # Check for web system indicators
            is_web = False
            if any(pattern in path.name.lower() for pattern in web_patterns):
                is_web = True
            elif (path / 'main.py').exists() and (path / 'static').exists():
                is_web = True
            elif (path / 'services' / 'json_db.py').exists():
                is_web = True
            
            if is_web:
                found_dirs['web'].append(path_str)
                continue
            
            # Check for PyQt system indicators
            is_pyqt = False
            if any(pattern in path.name.lower() for pattern in pyqt_patterns):
                is_pyqt = True
            elif (path / 'ui' / 'main_window.py').exists():
                is_pyqt = True
            elif (path / 'detection' / 'yolo_detector.py').exists():
                is_pyqt = True
            elif (path / 'models' / 'product.py').exists() and (path / 'ui').exists():
                is_pyqt = True
            
            if is_pyqt:
                found_dirs['pyqt'].append(path_str)
                continue
            
            # Check if it's a project directory (has Python files)
            py_files = list(path.glob('*.py'))
            if py_files and len(path_str.split(os.sep)) <= 2:  # Not too deep
                found_dirs['other'].append(path_str)
    
    return found_dirs

def display_found_directories(found_dirs):
    """Display found directories in a nice format"""
    print("="*60)
    print("📁 FOUND DIRECTORIES")
    print("="*60)
    
    if found_dirs['web']:
        print("\n🌐 Potential Web System Directories:")
        for i, dir_path in enumerate(found_dirs['web'], 1):
            print(f"   {i}. {dir_path}")
            # Check for key files
            path = Path(dir_path)
            if (path / 'main.py').exists():
                print(f"      ✓ Has main.py")
            if (path / 'static').exists():
                print(f"      ✓ Has static folder")
            if (path / 'services').exists():
                print(f"      ✓ Has services folder")
    else:
        print("\n❌ No web system directories found")
    
    if found_dirs['pyqt']:
        print("\n🖥️ Potential PyQt System Directories:")
        for i, dir_path in enumerate(found_dirs['pyqt'], 1):
            print(f"   {i}. {dir_path}")
            # Check for key files
            path = Path(dir_path)
            if (path / 'main.py').exists():
                print(f"      ✓ Has main.py")
            if (path / 'ui' / 'main_window.py').exists():
                print(f"      ✓ Has ui/main_window.py")
            if (path / 'detection').exists():
                print(f"      ✓ Has detection folder")
    else:
        print("\n❌ No PyQt system directories found")
    
    if found_dirs['other']:
        print("\n📂 Other Python Project Directories:")
        for dir_path in found_dirs['other'][:10]:  # Limit to 10
            print(f"   • {dir_path}")
    
    print("\n" + "="*60)

def get_user_selection(found_dirs):
    """Get user to select the correct directories"""
    selected = {}
    
    # Select web directory
    print("\n🌐 SELECT WEB SYSTEM DIRECTORY")
    print("-"*40)
    
    if found_dirs['web']:
        print("Found these potential web directories:")
        for i, dir_path in enumerate(found_dirs['web'], 1):
            print(f"  {i}. {dir_path}")
        print(f"  {len(found_dirs['web'])+1}. Enter custom path")
        
        while True:
            choice = input(f"\nSelect (1-{len(found_dirs['web'])+1}): ").strip()
            try:
                choice_num = int(choice)
                if 1 <= choice_num <= len(found_dirs['web']):
                    selected['web'] = found_dirs['web'][choice_num-1]
                    break
                elif choice_num == len(found_dirs['web'])+1:
                    custom = input("Enter web system path: ").strip()
                    if Path(custom).exists():
                        selected['web'] = custom
                        break
                    else:
                        print(f"❌ Path not found: {custom}")
            except:
                print("Invalid choice")
    else:
        custom = input("No web directories found. Enter web system path (or press Enter to skip): ").strip()
        if custom and Path(custom).exists():
            selected['web'] = custom
    
    # Select PyQt directory
    print("\n🖥️ SELECT PYQT SYSTEM DIRECTORY")
    print("-"*40)
    
    if found_dirs['pyqt']:
        print("Found these potential PyQt directories:")
        for i, dir_path in enumerate(found_dirs['pyqt'], 1):
            print(f"  {i}. {dir_path}")
        print(f"  {len(found_dirs['pyqt'])+1}. Enter custom path")
        
        while True:
            choice = input(f"\nSelect (1-{len(found_dirs['pyqt'])+1}): ").strip()
            try:
                choice_num = int(choice)
                if 1 <= choice_num <= len(found_dirs['pyqt']):
                    selected['pyqt'] = found_dirs['pyqt'][choice_num-1]
                    break
                elif choice_num == len(found_dirs['pyqt'])+1:
                    custom = input("Enter PyQt system path: ").strip()
                    if Path(custom).exists():
                        selected['pyqt'] = custom
                        break
                    else:
                        print(f"❌ Path not found: {custom}")
            except:
                print("Invalid choice")
    else:
        custom = input("No PyQt directories found. Enter PyQt system path (or press Enter to skip): ").strip()
        if custom and Path(custom).exists():
            selected['pyqt'] = custom
    
    return selected

def save_config(selected):
    """Save the configuration for future use"""
    config = {
        'web_dir': selected.get('web', ''),
        'pyqt_dir': selected.get('pyqt', '')
    }
    
    with open('hybrid_config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    
    print(f"\n✅ Configuration saved to hybrid_config.json")

def create_launcher(selected):
    """Create a custom launcher script"""
    if not selected.get('web') or not selected.get('pyqt'):
        print("\n⚠️  Cannot create launcher - missing directories")
        return
    
    launcher_content = f'''#!/usr/bin/env python3
"""
CUSTOM HYBRID LAUNCHER
Auto-generated for your system
"""

import os
import sys
import subprocess
import time
import signal

web_dir = r"{selected['web']}"
pyqt_dir = r"{selected['pyqt']}"

web_process = None
pyqt_process = None

def cleanup(signum=None, frame=None):
    global web_process, pyqt_process
    print("\\nShutting down...")
    
    if pyqt_process:
        pyqt_process.terminate()
    if web_process:
        web_process.terminate()
    
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup)

print("="*60)
print("STARTING HYBRID SMART CHECKOUT SYSTEM")
print("="*60)
print(f"Web:  {{web_dir}}")
print(f"PyQt: {{pyqt_dir}}")
print("="*60)

# Start web server
print("\\nStarting web server...")
os.chdir(web_dir)
web_process = subprocess.Popen([sys.executable, "main.py"])
os.chdir("..")

# Wait for server
print("Waiting for web server...")
time.sleep(5)

# Start PyQt
print("Starting PyQt scanner...")
os.chdir(pyqt_dir)
pyqt_process = subprocess.Popen([sys.executable, "main.py"])

print("\\n✅ Both systems are running!")
print("\\nWeb Interface: http://localhost:8000/cart")
print("\\nPress Ctrl+C to stop both systems")

try:
    pyqt_process.wait()
    print("\\nPyQt closed. Stopping web server...")
    web_process.terminate()
except KeyboardInterrupt:
    cleanup()
'''
    
    with open('launch_hybrid.py', 'w', encoding='utf-8') as f:
        f.write(launcher_content)
    
    # Make executable on Unix
    if os.name != 'nt':
        os.chmod('launch_hybrid.py', 0o755)
    
    print(f"✅ Custom launcher created: launch_hybrid.py")

def main():
    print("\n" + "="*60)
    print("🔍 HYBRID SYSTEM - DIRECTORY FINDER & SETUP")
    print("="*60)
    
    # Check for existing config
    if Path('hybrid_config.json').exists():
        print("\n📋 Found existing configuration!")
        with open('hybrid_config.json', 'r') as f:
            config = json.load(f)
        print(f"   Web:  {config['web_dir']}")
        print(f"   PyQt: {config['pyqt_dir']}")
        
        use_existing = input("\nUse this configuration? (y/n): ").strip().lower()
        if use_existing == 'y':
            create_launcher(config)
            print("\n✅ Run 'python launch_hybrid.py' to start the system!")
            return
    
    # Find directories
    found_dirs = find_all_directories()
    display_found_directories(found_dirs)
    
    # Get user selection
    selected = get_user_selection(found_dirs)
    
    if not selected.get('web') or not selected.get('pyqt'):
        print("\n❌ Both directories are required for the hybrid system")
        print("\nPlease ensure you have:")
        print("1. The web system (FastAPI with main.py)")
        print("2. The PyQt scanner system")
        return
    
    # Display selection
    print("\n" + "="*60)
    print("✅ SELECTED DIRECTORIES")
    print("="*60)
    print(f"Web System:  {selected['web']}")
    print(f"PyQt System: {selected['pyqt']}")
    
    # Save configuration
    save_config(selected)
    
    # Create launcher
    create_launcher(selected)
    
    print("\n" + "="*60)
    print("✅ SETUP COMPLETE!")
    print("="*60)
    print("\nTo start the hybrid system, run:")
    print("   python launch_hybrid.py")
    print("\nThis will start both systems automatically!")
    print("="*60)

if __name__ == "__main__":
    main()