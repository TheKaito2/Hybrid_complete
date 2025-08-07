#!/usr/bin/env python3
"""
Smart Self-Checkout System
A YOLO-based product detection system for convenience store self-checkout
"""

import sys
import os
import json
import logging
from pathlib import Path
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from ui.main_window import MainWindow


def setup_logging():
    """Setup logging configuration"""
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / "app.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger(__name__)


def check_requirements():
    """Check if all required files and directories exist"""
    required_dirs = [
        "config",
        "database", 
        "models",
        "detection",
        "ui",
        "utils",
        "assets",
        "trained_models",
        "logs"
    ]
    
    required_files = [
        "config/settings.json",
        "database/products.json"
    ]
    
    # Create directories if they don't exist
    for dir_name in required_dirs:
        dir_path = project_root / dir_name
        if not dir_path.exists():
            print(f"Creating directory: {dir_path}")
            dir_path.mkdir(exist_ok=True)
            
            # Create __init__.py for Python packages
            if dir_name not in ["assets", "trained_models", "logs"]:
                init_file = dir_path / "__init__.py"
                init_file.touch()
    
    # Check for required files
    missing_files = []
    for file_name in required_files:
        file_path = project_root / file_name
        if not file_path.exists():
            missing_files.append(file_name)
    
    if missing_files:
        print("\nWarning: The following required files are missing:")
        for file in missing_files:
            print(f"  - {file}")
        print("\nPlease ensure these files exist before running the application.")
        return False
    
    return True


def main():
    """Main application entry point"""
    # Setup logging
    logger = setup_logging()
    logger.info("Starting Smart Self-Checkout System")
    
    # Check requirements
    if not check_requirements():
        logger.error("Missing required files. Please check the setup.")
        sys.exit(1)
    
    # Create Qt application
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Enable high DPI support
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    try:
        # Create and show main window
        window = MainWindow()
        window.show()
        
        # Run application
        logger.info("Application started successfully")
        sys.exit(app.exec_())
        
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
