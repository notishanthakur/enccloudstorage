#!/usr/bin/env python3
"""
EncCloudStorage Startup Script
Quick start script for development and testing.
"""

import os
import sys
import subprocess
from pathlib import Path

def check_requirements():
    """Check if all requirements are installed."""
    try:
        import flask
        import sqlalchemy
        import cryptography
        import stegano
        print("[SUCCESS] All required packages are installed")
        return True
    except ImportError as e:
        print("[ERROR] Missing required package: {}".format(e))
        print("Please run: pip install -r requirements.txt")
        return False

def setup_database():
    """Initialize the database."""
    try:
        from app import app, db
        with app.app_context():
            db.create_all()
            print("[SUCCESS] Database initialized")
            return True
    except Exception as e:
        print("[ERROR] Database setup failed: {}".format(e))
        return False

def create_directories():
    """Create necessary directories."""
    directories = ['uploads', 'static/css', 'static/js', 'templates']
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
    print("[SUCCESS] Directories created")

def main():
    """Main startup function."""
    print("[STARTUP] EncCloudStorage Startup")
    print("=" * 50)
    
    # Check requirements
    if not check_requirements():
        sys.exit(1)
    
    # Create directories
    create_directories()
    
    # Setup database
    if not setup_database():
        sys.exit(1)
    
    # Check for profile image
    if not os.path.exists('profile.png'):
        print("[WARNING] Profile image not found. Creating default...")
        try:
            from PIL import Image
            img = Image.new('RGB', (200, 200), color='lightblue')
            img.save('profile.png')
            print("[SUCCESS] Default profile image created")
        except ImportError:
            print("[ERROR] PIL not available. Please install Pillow: pip install Pillow")
    
    print("\n[SUCCESS] Setup complete!")
    print("\n[GUIDE] Quick Start Guide:")
    print("1. Run: python run.py")
    print("2. Open: http://localhost:5000")
    print("3. Login: admin / admin123")
    print("\n[SECURITY] Security Features:")
    print("- AES-256 Encryption")
    print("- Searchable Encryption") 
    print("- Steganographic Key Storage")
    print("- Zero-Knowledge Architecture")
    
    # Ask if user wants to start the server
    response = input("\n[PROMPT] Start the server now? (y/n): ").lower().strip()
    if response in ['y', 'yes']:
        print("\n[STARTUP] Starting EncCloudStorage server...")
        os.system("python run.py")
    else:
        print("\n[INFO] Run 'python run.py' when ready to start!")

if __name__ == '__main__':
    main()
