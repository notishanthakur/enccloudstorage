#!/bin/bash
# EncCloudStorage WSL Setup Script

echo "=== EncCloudStorage WSL Setup ==="

# Update package list
echo "Updating package list..."
sudo apt update

# Install Python and pip
echo "Installing Python and pip..."
sudo apt install -y python3 python3-pip python3-venv

# Install system dependencies
echo "Installing system dependencies..."
sudo apt install -y libpq-dev python3-dev build-essential

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv enccloudstorage_env
source enccloudstorage_env/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install Python dependencies
echo "Installing Python dependencies..."
pip install Flask==2.3.3
pip install Flask-SQLAlchemy==3.0.5
pip install Flask-Login==0.6.3
pip install Flask-WTF==1.1.1
pip install WTForms==3.0.1
pip install Werkzeug==2.3.7
pip install pycryptodome==3.19.0
pip install stegano==1.1.3
pip install Pillow==10.0.1
pip install python-dotenv==1.0.0
pip install gunicorn==21.2.0
pip install psycopg2-binary==2.9.7
pip install alembic==1.12.1

# Install Azure SDK (optional)
echo "Installing Azure SDK..."
pip install azure-storage-blob==12.19.0
pip install azure-identity==1.15.0

echo "=== Setup Complete ==="
echo "To activate the environment: source enccloudstorage_env/bin/activate"
echo "To run the application: python3 run.py"
