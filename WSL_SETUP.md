# EncCloudStorage WSL Setup Guide

## Quick Setup in WSL

### Option 1: Copy Files to WSL

1. **Open WSL terminal** and navigate to your home directory:
   ```bash
   cd ~
   ```

2. **Copy the project files** from Windows to WSL:
   ```bash
   # From Windows PowerShell/CMD, copy files to WSL
   wsl cp -r /mnt/c/Users/Ishan\ Thakur/enccloudstorage ~/enccloudstorage
   ```

3. **Navigate to the project directory**:
   ```bash
   cd ~/enccloudstorage
   ```

4. **Run the setup script**:
   ```bash
   chmod +x setup_wsl.sh
   ./setup_wsl.sh
   ```

5. **Activate the virtual environment**:
   ```bash
   source enccloudstorage_env/bin/activate
   ```

6. **Run the application**:
   ```bash
   python3 run.py
   ```

### Option 2: Manual Setup

If the copy doesn't work, you can manually recreate the project:

1. **Create project directory**:
   ```bash
   mkdir ~/enccloudstorage
   cd ~/enccloudstorage
   ```

2. **Install dependencies**:
   ```bash
   sudo apt update
   sudo apt install -y python3 python3-pip python3-venv libpq-dev python3-dev build-essential
   ```

3. **Create virtual environment**:
   ```bash
   python3 -m venv enccloudstorage_env
   source enccloudstorage_env/bin/activate
   ```

4. **Install Python packages**:
   ```bash
   pip install Flask Flask-SQLAlchemy Flask-Login Flask-WTF WTForms Werkzeug pycryptodome stegano Pillow python-dotenv azure-storage-blob azure-identity
   ```

5. **Copy the application files** from Windows to WSL (you'll need to manually copy the Python files)

### Option 3: Use Windows Terminal with WSL

1. **Open Windows Terminal**
2. **Select WSL tab**
3. **Navigate to Windows files**:
   ```bash
   cd /mnt/c/Users/Ishan\ Thakur/enccloudstorage
   ```

4. **Install Python dependencies**:
   ```bash
   sudo apt update
   sudo apt install -y python3 python3-pip
   pip3 install Flask Flask-SQLAlchemy Flask-Login Flask-WTF WTForms Werkzeug pycryptodome stegano Pillow python-dotenv azure-storage-blob azure-identity
   ```

5. **Run the application**:
   ```bash
   python3 run.py
   ```

## Troubleshooting

### If Python is not found:
```bash
sudo apt install python3 python3-pip
```

### If pip is not found:
```bash
sudo apt install python3-pip
```

### If you get permission errors:
```bash
sudo chmod +x setup_wsl.sh
```

### If you get import errors:
```bash
pip3 install --upgrade pip
pip3 install -r requirements.txt
```

## Accessing the Application

Once running, the application will be available at:
- **Local**: http://localhost:5000
- **From Windows**: http://localhost:5000 (same as local)

## Default Login

- **Username**: admin
- **Password**: admin123

## Features Available

- ✅ File upload with AES-256 encryption
- ✅ Searchable encryption
- ✅ Steganographic key storage
- ✅ User authentication
- ✅ Admin panel
- ✅ Activity logging
- ✅ Modern web interface

## Next Steps

1. **Test the application** by uploading a file
2. **Try the search functionality**
3. **Check the admin panel** (login as admin)
4. **Configure Azure Blob Storage** (optional)
5. **Deploy to production** (optional)
