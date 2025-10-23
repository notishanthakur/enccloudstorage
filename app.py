from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import json
import hashlib
import logging
from datetime import datetime
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from stegano import lsb
try:
    from azure.storage.blob import BlobServiceClient
    from azure.identity import DefaultAzureCredential
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    print("⚠️  Azure SDK not available. Using local storage fallback.")
import io

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///enccloudstorage.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Azure Blob Storage configuration
AZURE_STORAGE_ACCOUNT_NAME = os.environ.get('AZURE_STORAGE_ACCOUNT_NAME')
AZURE_STORAGE_CONTAINER_NAME = os.environ.get('AZURE_STORAGE_CONTAINER_NAME', 'enccloudstorage')
AZURE_STORAGE_ACCOUNT_KEY = os.environ.get('AZURE_STORAGE_ACCOUNT_KEY')

# Initialize Azure Blob Service Client
blob_service_client = None
if AZURE_AVAILABLE and AZURE_STORAGE_ACCOUNT_NAME:
    try:
        if AZURE_STORAGE_ACCOUNT_KEY:
            blob_service_client = BlobServiceClient(
                account_url=f"https://{AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net",
                credential=AZURE_STORAGE_ACCOUNT_KEY
            )
        else:
            # Use DefaultAzureCredential for managed identity
            credential = DefaultAzureCredential()
            blob_service_client = BlobServiceClient(
                account_url=f"https://{AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net",
                credential=credential
            )
        logger.info("Azure Blob Storage client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Azure Blob Storage: {e}")
        blob_service_client = None
else:
    logger.info("Azure Blob Storage not configured. Using local storage fallback.")

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    user_level = db.Column(db.String(20), default='user')  # 'admin' or 'user'
    profile_image = db.Column(db.String(255))  # Plain profile image (server-side)
    stego_image = db.Column(db.String(255))    # Steganographic image (client-side only)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    files = db.relationship('File', backref='owner', lazy=True)
    logs = db.relationship('ActivityLog', backref='user', lazy=True)

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    blob_name = db.Column(db.String(255), nullable=False)  # Azure blob name
    file_size = db.Column(db.Integer)
    encrypted_key = db.Column(db.Text)  # AES key (encrypted)
    keywords_hash = db.Column(db.Text)  # JSON of hashed keywords
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_encrypted = db.Column(db.Boolean, default=True)
    access_level = db.Column(db.String(20), default='private')  # 'private', 'shared', 'public'

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)  # 'upload', 'download', 'search', 'decrypt'
    resource = db.Column(db.String(255))  # File name or search term
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    success = db.Column(db.Boolean, default=True)
    details = db.Column(db.Text)  # Additional details in JSON format

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Utility Functions
def pad(data: bytes) -> bytes:
    """Pad plaintext to be multiple of 16 bytes (AES block size)."""
    return data + b"\0" * (AES.block_size - len(data) % AES.block_size)

def encrypt_file(file_data: bytes, key: bytes) -> bytes:
    """Encrypt file contents with AES."""
    cipher = AES.new(key, AES.MODE_CBC)
    ciphertext = cipher.encrypt(pad(file_data))
    return cipher.iv + ciphertext

def decrypt_file(ciphertext: bytes, key: bytes) -> bytes:
    """Decrypt AES-encrypted file contents."""
    iv = ciphertext[:AES.block_size]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    plaintext = cipher.decrypt(ciphertext[AES.block_size:])
    return plaintext.rstrip(b"\0")

def extract_keywords(text: str) -> list:
    """Extract keywords from text with improved NLP-like processing."""
    import re
    
    # Convert to lowercase and clean text
    text = text.lower()
    
    # Remove special characters but keep spaces
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # Split into words
    words = text.split()
    
    # Enhanced stopwords list
    stopwords = {
        "the", "a", "an", "is", "and", "of", "to", "in", "for", "with", "on", "at", "by", "from", "up", "about", "into", "through", "during", "before", "after", "above", "below", "between", "among",
        "this", "that", "these", "those", "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us", "them",
        "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "can", "must",
        "be", "been", "being", "am", "are", "was", "were", "get", "got", "make", "made", "take", "took", "come", "came",
        "go", "went", "see", "saw", "know", "knew", "think", "thought", "say", "said", "tell", "told", "want", "wanted",
        "need", "needed", "use", "used", "work", "worked", "call", "called", "try", "tried", "ask", "asked", "feel", "felt"
    }
    
    # Extract meaningful keywords
    keywords = []
    for word in words:
        word = word.strip()
        if len(word) > 2 and word not in stopwords and word.isalpha():
            keywords.append(word)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_keywords = []
    for keyword in keywords:
        if keyword not in seen:
            seen.add(keyword)
            unique_keywords.append(keyword)
    
    return unique_keywords

def hash_keyword(word: str) -> str:
    """Hash keyword with SHA-256."""
    return hashlib.sha256(word.encode()).hexdigest()

def log_activity(user_id: int, action: str, resource: str = None, success: bool = True, details: str = None):
    """Log user activity to database."""
    try:
        log_entry = ActivityLog(
            user_id=user_id,
            action=action,
            resource=resource,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            success=success,
            details=details
        )
        db.session.add(log_entry)
        db.session.commit()
        logger.info(f"Activity logged: {action} by user {user_id}")
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            if not user.is_active:
                flash('Account is deactivated. Please contact administrator.', 'error')
                return render_template('login.html')
            
            login_user(user)
            log_activity(user.id, 'login', success=True)
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            log_activity(user.id if user else None, 'login', success=False, details='Invalid credentials')
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('register.html')
        
        # Create new user
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            user_level='user'  # Default to regular user
        )
        
        db.session.add(user)
        db.session.commit()
        
        log_activity(user.id, 'register', success=True)
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    log_activity(current_user.id, 'logout', success=True)
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    user_files = File.query.filter_by(user_id=current_user.id).order_by(File.upload_date.desc()).limit(10).all()
    recent_logs = ActivityLog.query.filter_by(user_id=current_user.id).order_by(ActivityLog.timestamp.desc()).limit(5).all()
    
    return render_template('dashboard.html', files=user_files, logs=recent_logs)

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if file:
            try:
                # Generate AES key
                aes_key = get_random_bytes(32)
                
                # Read file data
                file_data = file.read()
                original_filename = secure_filename(file.filename)
                
                # Encrypt file
                encrypted_data = encrypt_file(file_data, aes_key)
                
                # Extract keywords from file content (for text files)
                keywords = []
                if original_filename.lower().endswith(('.txt', '.md', '.py', '.js', '.html', '.css')):
                    try:
                        text_content = file_data.decode('utf-8')
                        keywords = extract_keywords(text_content)
                    except:
                        keywords = extract_keywords(original_filename)
                else:
                    keywords = extract_keywords(original_filename)
                
                # Create keyword hash map
                keyword_hashes = {hash_keyword(kw): True for kw in keywords}
                
                # Upload to Azure Blob Storage
                blob_name = f"user_{current_user.id}/{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{original_filename}.enc"
                
                if blob_service_client:
                    blob_client = blob_service_client.get_blob_client(
                        container=AZURE_STORAGE_CONTAINER_NAME,
                        blob=blob_name
                    )
                    blob_client.upload_blob(encrypted_data, overwrite=True)
                else:
                    # Fallback to local storage for development
                    # Create the full directory path
                    upload_path = f'uploads/user_{current_user.id}'
                    os.makedirs(upload_path, exist_ok=True)
                    full_path = f'{upload_path}/{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}_{original_filename}.enc'
                    with open(full_path, 'wb') as f:
                        f.write(encrypted_data)
                
                # Store file record in database
                file_record = File(
                    filename=blob_name,
                    original_filename=original_filename,
                    blob_name=blob_name,
                    file_size=len(file_data),  # Original file size
                    encrypted_key=aes_key.hex(),
                    keywords_hash=json.dumps(keyword_hashes),
                    user_id=current_user.id,
                    access_level=request.form.get('access_level', 'private')
                )
                
                db.session.add(file_record)
                db.session.commit()
                
                # Update user's stego image with new key and index
                update_stego_image(current_user.id)
                
                log_activity(current_user.id, 'upload', resource=original_filename, success=True)
                flash(f'File "{original_filename}" uploaded and encrypted successfully!', 'success')
                return redirect(url_for('dashboard'))
                
            except Exception as e:
                logger.error(f"Upload error: {e}")
                log_activity(current_user.id, 'upload', resource=file.filename, success=False, details=str(e))
                flash(f'Error uploading file: {str(e)}', 'error')
    
    return render_template('upload.html')

def update_stego_image(user_id: int):
    """Update user's steganographic image with current keys and indexes."""
    try:
        user = User.query.get(user_id)
        if not user:
            return
        
        # Get all user's files and their keywords
        user_files = File.query.filter_by(user_id=user_id).all()
        
        # Build comprehensive index
        master_index = {}
        master_keys = {}
        
        for file_record in user_files:
            # Add file to master index
            keywords = json.loads(file_record.keywords_hash)
            for keyword_hash in keywords.keys():
                master_index[keyword_hash] = file_record.blob_name
            
            # Store encrypted key
            master_keys[file_record.blob_name] = file_record.encrypted_key
        
        # Create payload
        payload = {
            "user_id": user_id,
            "index": master_index,
            "keys": master_keys,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Use default profile image or create one
        profile_img_path = user.profile_image or 'profile.png'
        if not os.path.exists(profile_img_path):
            # Create a simple default profile image
            try:
                from PIL import Image
                img = Image.new('RGB', (200, 200), color='lightblue')
                img.save(profile_img_path)
                logger.info(f"Created default profile image: {profile_img_path}")
            except ImportError:
                logger.error("PIL not available. Cannot create profile image.")
                return
        
        # Embed data in image
        try:
            payload_str = json.dumps(payload)
            stego_image = lsb.hide(profile_img_path, payload_str)
        except Exception as e:
            logger.error(f"Error creating steganographic image: {e}")
            # Fallback: just save the profile image without steganography
            user.stego_image = profile_img_path
            db.session.commit()
            return
        
        # Save stego image
        stego_path = f"stego_user_{user_id}.png"
        stego_image.save(stego_path)
        
        # Update user record
        user.stego_image = stego_path
        db.session.commit()
        
        logger.info(f"Updated stego image for user {user_id}: {stego_path}")
        
    except Exception as e:
        logger.error(f"Failed to update stego image: {e}")

@app.route('/search', methods=['GET', 'POST'])
@login_required
def search_files():
    if request.method == 'POST':
        search_term = request.form.get('search_term', '').strip()
        if not search_term:
            flash('Please enter a search term', 'error')
            return render_template('search.html')
        
        try:
            # Hash the search term
            search_hash = hash_keyword(search_term.lower())
            
            # Extract data from stego image
            user = User.query.get(current_user.id)
            if not user.stego_image or not os.path.exists(user.stego_image):
                flash('No encrypted data found. Please upload some files first.', 'error')
                return render_template('search.html')
            
            try:
                hidden_payload = lsb.reveal(user.stego_image)
                if not hidden_payload:
                    flash('No hidden data found in steganographic image.', 'error')
                    return render_template('search.html')
                
                payload = json.loads(hidden_payload)
            except json.JSONDecodeError as e:
                flash(f'Invalid steganographic data: {str(e)}', 'error')
                return render_template('search.html')
            except Exception as e:
                flash(f'Error reading steganographic data: {str(e)}', 'error')
                return render_template('search.html')
            
            # Search in index
            matches = []
            if search_hash in payload.get('index', {}):
                blob_name = payload['index'][search_hash]
                # Find file record
                file_record = File.query.filter_by(blob_name=blob_name, user_id=current_user.id).first()
                if file_record:
                    matches.append({
                        'id': file_record.id,
                        'filename': file_record.original_filename,
                        'upload_date': file_record.upload_date,
                        'file_size': file_record.file_size
                    })
            
            log_activity(current_user.id, 'search', resource=search_term, success=True, details=f"Found {len(matches)} matches")
            
            return render_template('search.html', matches=matches, search_term=search_term)
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            log_activity(current_user.id, 'search', resource=search_term, success=False, details=str(e))
            flash(f'Search error: {str(e)}', 'error')
    
    return render_template('search.html')

@app.route('/download/<int:file_id>')
@login_required
def download_file(file_id):
    try:
        file_record = File.query.filter_by(id=file_id, user_id=current_user.id).first()
        if not file_record:
            flash('File not found', 'error')
            return redirect(url_for('dashboard'))
        
        # Extract key from stego image
        user = User.query.get(current_user.id)
        if not user.stego_image or not os.path.exists(user.stego_image):
            flash('Cannot decrypt: No encryption data found', 'error')
            return redirect(url_for('dashboard'))
        
        try:
            hidden_payload = lsb.reveal(user.stego_image)
            if not hidden_payload:
                flash('Cannot decrypt: No hidden data found in steganographic image', 'error')
                return redirect(url_for('dashboard'))
            
            payload = json.loads(hidden_payload)
        except json.JSONDecodeError as e:
            flash(f'Cannot decrypt: Invalid steganographic data: {str(e)}', 'error')
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f'Cannot decrypt: Error reading steganographic data: {str(e)}', 'error')
            return redirect(url_for('dashboard'))
        
        if file_record.blob_name not in payload.get('keys', {}):
            flash('Cannot decrypt: Key not found', 'error')
            return redirect(url_for('dashboard'))
        
        # Get encrypted key
        encrypted_key_hex = payload['keys'][file_record.blob_name]
        aes_key = bytes.fromhex(encrypted_key_hex)
        
        # Download from Azure Blob Storage
        if blob_service_client:
            blob_client = blob_service_client.get_blob_client(
                container=AZURE_STORAGE_CONTAINER_NAME,
                blob=file_record.blob_name
            )
            encrypted_data = blob_client.download_blob().readall()
        else:
            # Fallback to local storage
            local_path = f'uploads/{file_record.blob_name}'
            if not os.path.exists(local_path):
                flash('File not found on server', 'error')
                return redirect(url_for('dashboard'))
            with open(local_path, 'rb') as f:
                encrypted_data = f.read()
        
        # Decrypt file
        decrypted_data = decrypt_file(encrypted_data, aes_key)
        
        # Log activity
        log_activity(current_user.id, 'download', resource=file_record.original_filename, success=True)
        
        # Return file
        from flask import Response
        return Response(
            decrypted_data,
            mimetype='application/octet-stream',
            headers={'Content-Disposition': f'attachment; filename={file_record.original_filename}'}
        )
        
    except Exception as e:
        logger.error(f"Download error: {e}")
        log_activity(current_user.id, 'download', resource=f"file_id_{file_id}", success=False, details=str(e))
        flash(f'Download error: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

@app.route('/delete/<int:file_id>')
@login_required
def delete_file(file_id):
    """Delete a file (user can only delete their own files)."""
    try:
        file_record = File.query.filter_by(id=file_id, user_id=current_user.id).first()
        if not file_record:
            flash('File not found or access denied', 'error')
            return redirect(url_for('dashboard'))
        
        # Delete physical file
        if blob_service_client:
            try:
                blob_client = blob_service_client.get_blob_client(
                    container=AZURE_STORAGE_CONTAINER_NAME,
                    blob=file_record.blob_name
                )
                blob_client.delete_blob()
            except Exception as e:
                logger.warning(f"Could not delete blob from Azure: {e}")
        else:
            # Delete from local storage
            local_path = f'uploads/{file_record.blob_name}'
            if os.path.exists(local_path):
                os.remove(local_path)
        
        # Delete database record
        db.session.delete(file_record)
        db.session.commit()
        
        # Update steganographic image to remove deleted file's keys
        update_stego_image(current_user.id)
        
        log_activity(current_user.id, 'delete', resource=file_record.original_filename, success=True)
        flash(f'File "{file_record.original_filename}" deleted successfully!', 'success')
        
    except Exception as e:
        logger.error(f"Delete error: {e}")
        log_activity(current_user.id, 'delete', resource=f"file_id_{file_id}", success=False, details=str(e))
        flash(f'Error deleting file: {str(e)}', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/admin/delete/<int:file_id>')
@login_required
def admin_delete_file(file_id):
    """Admin can delete any file."""
    if current_user.user_level != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        file_record = File.query.get_or_404(file_id)
        
        # Delete physical file
        if blob_service_client:
            try:
                blob_client = blob_service_client.get_blob_client(
                    container=AZURE_STORAGE_CONTAINER_NAME,
                    blob=file_record.blob_name
                )
                blob_client.delete_blob()
            except Exception as e:
                logger.warning(f"Could not delete blob from Azure: {e}")
        else:
            # Delete from local storage
            local_path = f'uploads/{file_record.blob_name}'
            if os.path.exists(local_path):
                os.remove(local_path)
        
        # Delete database record
        db.session.delete(file_record)
        db.session.commit()
        
        # Update steganographic image for the file owner
        update_stego_image(file_record.user_id)
        
        log_activity(current_user.id, 'admin_delete', resource=file_record.original_filename, success=True)
        flash(f'File "{file_record.original_filename}" deleted by admin!', 'success')
        
    except Exception as e:
        logger.error(f"Admin delete error: {e}")
        log_activity(current_user.id, 'admin_delete', resource=f"file_id_{file_id}", success=False, details=str(e))
        flash(f'Error deleting file: {str(e)}', 'error')
    
    return redirect(url_for('admin_panel'))

@app.route('/admin/user/<int:user_id>')
@login_required
def admin_user_details(user_id):
    """Admin view of specific user details."""
    if current_user.user_level != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    user_files = File.query.filter_by(user_id=user_id).order_by(File.upload_date.desc()).all()
    user_activities = ActivityLog.query.filter_by(user_id=user_id).order_by(ActivityLog.timestamp.desc()).all()
    
    return render_template('admin_user_details.html', 
                         user=user, 
                         user_files=user_files,
                         user_activities=user_activities)

@app.route('/admin/logs')
@login_required
def admin_all_logs():
    """Admin view of all system logs with advanced filtering."""
    if current_user.user_level != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    # Get filter parameters
    user_filter = request.args.get('user_id', type=int)
    action_filter = request.args.get('action', '')
    success_filter = request.args.get('success', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    # Build query
    query = ActivityLog.query
    
    if user_filter:
        query = query.filter_by(user_id=user_filter)
    if action_filter:
        query = query.filter(ActivityLog.action.contains(action_filter))
    if success_filter:
        query = query.filter_by(success=success_filter == 'true')
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(ActivityLog.timestamp >= from_date)
        except ValueError:
            pass
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d')
            query = query.filter(ActivityLog.timestamp <= to_date)
        except ValueError:
            pass
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 100
    logs_pagination = query.order_by(ActivityLog.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get all users for filter dropdown
    all_users = User.query.all()
    
    return render_template('admin_logs.html', 
                         logs_pagination=logs_pagination,
                         all_users=all_users,
                         current_filters={
                             'user_id': user_filter,
                             'action': action_filter,
                             'success': success_filter,
                             'date_from': date_from,
                             'date_to': date_to
                         })

@app.route('/admin/export/logs')
@login_required
def admin_export_logs():
    """Export all logs to CSV."""
    if current_user.user_level != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        import csv
        from io import StringIO
        
        # Get all logs
        logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).all()
        
        # Create CSV
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Timestamp', 'User', 'Action', 'Resource', 'IP Address', 'Success', 'Details'])
        
        # Write data
        for log in logs:
            writer.writerow([
                log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                log.user.username if log.user else 'Unknown',
                log.action,
                log.resource or '',
                log.ip_address or '',
                'Yes' if log.success else 'No',
                log.details or ''
            ])
        
        # Return CSV
        from flask import Response
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=system_logs.csv'}
        )
        
    except Exception as e:
        logger.error(f"Export logs error: {e}")
        flash(f'Error exporting logs: {str(e)}', 'error')
        return redirect(url_for('admin_panel'))

@app.route('/admin/stats')
@login_required
def admin_statistics():
    """Admin statistics and analytics."""
    if current_user.user_level != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    # Get comprehensive statistics
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    admin_users = User.query.filter_by(user_level='admin').count()
    
    total_files = File.query.count()
    total_size = db.session.query(db.func.sum(File.file_size)).scalar() or 0
    
    # Activity statistics
    total_activities = ActivityLog.query.count()
    successful_activities = ActivityLog.query.filter_by(success=True).count()
    failed_activities = ActivityLog.query.filter_by(success=False).count()
    
    # Recent activity by action
    from sqlalchemy import func
    activity_by_action = db.session.query(
        ActivityLog.action, 
        func.count(ActivityLog.id).label('count')
    ).group_by(ActivityLog.action).all()
    
    # User activity counts
    user_activity_counts = db.session.query(
        User.username,
        func.count(ActivityLog.id).label('activity_count')
    ).join(ActivityLog, User.id == ActivityLog.user_id).group_by(User.id, User.username).all()
    
    return render_template('admin_statistics.html',
                         total_users=total_users,
                         active_users=active_users,
                         admin_users=admin_users,
                         total_files=total_files,
                         total_size=total_size,
                         total_activities=total_activities,
                         successful_activities=successful_activities,
                         failed_activities=failed_activities,
                         activity_by_action=activity_by_action,
                         user_activity_counts=user_activity_counts)

@app.route('/static/images/<path:filename>')
def serve_image(filename):
    """Serve profile and steganographic images."""
    try:
        # Check if file exists
        if not os.path.exists(filename):
            return "Image not found", 404
        
        # Serve the image with proper headers
        return send_file(filename, mimetype='image/png')
    except Exception as e:
        logger.error(f"Error serving image {filename}: {e}")
        return "Error loading image", 500

@app.route('/debug/stego/<int:user_id>')
@login_required
def debug_stego_data(user_id):
    """Debug route to check steganographic data without displaying it."""
    # Allow users to check their own data, admins to check any user's data
    if current_user.user_level != 'admin' and current_user.id != user_id:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    if not user.stego_image or not os.path.exists(user.stego_image):
        return jsonify({'error': 'No steganographic image found'})
    
    try:
        hidden_data = lsb.reveal(user.stego_image)
        if not hidden_data:
            return jsonify({'error': 'No hidden data found'})
        
        payload = json.loads(hidden_data)
        return jsonify({
            'success': True,
            'keys_count': len(payload.get('keys', {})),
            'index_count': len(payload.get('index', {})),
            'user_id': payload.get('user_id'),
            'timestamp': payload.get('timestamp')
        })
    except Exception as e:
        return jsonify({'error': f'Error reading steganographic data: {str(e)}'})

@app.route('/user/stego-data/<int:user_id>')
@login_required
def user_stego_data(user_id):
    """Get full steganographic data for user display."""
    # Allow users to access their own data, admins to access any user's data
    if current_user.user_level != 'admin' and current_user.id != user_id:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    if not user.stego_image or not os.path.exists(user.stego_image):
        return jsonify({'error': 'No steganographic image found'})
    
    try:
        hidden_data = lsb.reveal(user.stego_image)
        if not hidden_data:
            return jsonify({'error': 'No hidden data found'})
        
        payload = json.loads(hidden_data)
        
        # Format the data similar to the example provided
        formatted_data = {
            'success': True,
            'keys': payload.get('keys', {}),
            'index': payload.get('index', {}),
            'keys_count': len(payload.get('keys', {})),
            'index_count': len(payload.get('index', {})),
            'user_id': payload.get('user_id'),
            'timestamp': payload.get('timestamp'),
            'raw_format': {
                'aes_key': list(payload.get('keys', {}).values())[0] if payload.get('keys', {}) else 'No key found',
                'index': payload.get('index', {})
            }
        }
        
        return jsonify(formatted_data)
    except Exception as e:
        return jsonify({'error': f'Error reading steganographic data: {str(e)}'})

@app.route('/user/hidden-message/<int:user_id>')
@login_required
def user_hidden_message(user_id):
    """Get the raw hidden message format for user display."""
    # Allow users to access their own data, admins to access any user's data
    if current_user.user_level != 'admin' and current_user.id != user_id:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    if not user.stego_image or not os.path.exists(user.stego_image):
        return jsonify({'error': 'No steganographic image found'})
    
    try:
        hidden_data = lsb.reveal(user.stego_image)
        if not hidden_data:
            return jsonify({'error': 'No hidden data found'})
        
        payload = json.loads(hidden_data)
        
        # Return in the exact format requested
        hidden_message = {
            "aes_key": list(payload.get('keys', {}).values())[0] if payload.get('keys', {}) else "No key found",
            "index": payload.get('index', {})
        }
        
        return jsonify(hidden_message)
    except Exception as e:
        return jsonify({'error': f'Error reading steganographic data: {str(e)}'})

@app.route('/admin/stego-overview')
@login_required
def admin_stego_overview():
    """Admin overview of all steganographic images and their data."""
    if current_user.user_level != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    # Get all users
    all_users = User.query.all()
    users_with_stego = []
    users_without_stego = []
    total_keys = 0
    total_indexes = 0
    
    for user in all_users:
        if user.stego_image and os.path.exists(user.stego_image):
            try:
                hidden_data = lsb.reveal(user.stego_image)
                if hidden_data:
                    payload = json.loads(hidden_data)
                    keys_count = len(payload.get('keys', {}))
                    index_count = len(payload.get('index', {}))
                    
                    users_with_stego.append({
                        'user': user,
                        'keys_count': keys_count,
                        'index_count': index_count,
                        'last_updated': payload.get('timestamp', 'Unknown')
                    })
                    
                    total_keys += keys_count
                    total_indexes += index_count
                else:
                    users_without_stego.append(user)
            except Exception as e:
                logger.warning(f"Could not read steganographic data for user {user.id}: {e}")
                users_without_stego.append(user)
        else:
            users_without_stego.append(user)
    
    return render_template('admin_stego_overview.html',
                         all_users=all_users,
                         users_with_stego=users_with_stego,
                         users_without_stego=users_without_stego,
                         total_keys=total_keys,
                         total_indexes=total_indexes)

@app.route('/admin/export/stego-data')
@login_required
def admin_export_stego_data():
    """Export all steganographic data for analysis."""
    if current_user.user_level != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        import csv
        from io import StringIO
        
        # Get all users with steganographic data
        all_users = User.query.all()
        stego_data = []
        
        for user in all_users:
            if user.stego_image and os.path.exists(user.stego_image):
                try:
                    hidden_data = lsb.reveal(user.stego_image)
                    if hidden_data:
                        payload = json.loads(hidden_data)
                        stego_data.append({
                            'user_id': user.id,
                            'username': user.username,
                            'email': user.email,
                            'stego_image_path': user.stego_image,
                            'keys_count': len(payload.get('keys', {})),
                            'index_count': len(payload.get('index', {})),
                            'last_updated': payload.get('timestamp', 'Unknown'),
                            'status': 'Valid'
                        })
                    else:
                        stego_data.append({
                            'user_id': user.id,
                            'username': user.username,
                            'email': user.email,
                            'stego_image_path': user.stego_image,
                            'keys_count': 0,
                            'index_count': 0,
                            'last_updated': 'Unknown',
                            'status': 'No Data'
                        })
                except Exception as e:
                    stego_data.append({
                        'user_id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'stego_image_path': user.stego_image,
                        'keys_count': 0,
                        'index_count': 0,
                        'last_updated': 'Unknown',
                        'status': f'Error: {str(e)[:50]}'
                    })
            else:
                stego_data.append({
                    'user_id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'stego_image_path': 'None',
                    'keys_count': 0,
                    'index_count': 0,
                    'last_updated': 'Never',
                    'status': 'No Image'
                })
        
        # Create CSV
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['User ID', 'Username', 'Email', 'Stego Image Path', 'Keys Count', 'Index Count', 'Last Updated', 'Status'])
        
        # Write data
        for data in stego_data:
            writer.writerow([
                data['user_id'],
                data['username'],
                data['email'],
                data['stego_image_path'],
                data['keys_count'],
                data['index_count'],
                data['last_updated'],
                data['status']
            ])
        
        # Return CSV
        from flask import Response
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=steganographic_data_analysis.csv'}
        )
        
    except Exception as e:
        logger.error(f"Export stego data error: {e}")
        flash(f'Error exporting steganographic data: {str(e)}', 'error')
        return redirect(url_for('admin_panel'))

@app.route('/admin')
@login_required
def admin_panel():
    if current_user.user_level != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    # Get all users and their activity
    users = User.query.all()
    all_activities = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).all()  # ALL logs, not just recent
    all_files = File.query.order_by(File.upload_date.desc()).all()
    total_files = File.query.count()
    total_users = User.query.count()
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 50  # Show 50 activities per page
    
    # Paginate activities
    activities_pagination = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin.html', 
                         users=users, 
                         activities=all_activities,
                         activities_pagination=activities_pagination,
                         all_files=all_files,
                         total_files=total_files,
                         total_users=total_users)

@app.route('/admin/user/<int:user_id>/toggle')
@login_required
def toggle_user_status(user_id):
    if current_user.user_level != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    
    log_activity(current_user.id, 'admin_action', resource=f"toggle_user_{user_id}", 
                success=True, details=f"User {user.username} {'activated' if user.is_active else 'deactivated'}")
    
    flash(f'User {user.username} {"activated" if user.is_active else "deactivated"}', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/profile')
@login_required
def profile():
    """User profile page showing steganographic image info."""
    user = User.query.get(current_user.id)
    stego_exists = user.stego_image and os.path.exists(user.stego_image)
    
    # Get user's file count
    file_count = File.query.filter_by(user_id=current_user.id).count()
    
    return render_template('profile.html', 
                         user=user, 
                         stego_exists=stego_exists,
                         file_count=file_count)

@app.route('/admin/stego/<int:user_id>')
@login_required
def view_stego_image(user_id):
    """Admin view of user's steganographic image."""
    if current_user.user_level != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    stego_path = user.stego_image
    
    if not stego_path or not os.path.exists(stego_path):
        flash('Steganographic image not found', 'error')
        return redirect(url_for('admin_panel'))
    
    # Try to reveal hidden data
    try:
        hidden_data = lsb.reveal(stego_path)
        if not hidden_data:
            flash('No hidden data found in image', 'error')
            return redirect(url_for('admin_panel'))
        
        payload = json.loads(hidden_data)
        return render_template('stego_view.html', 
                             user=user, 
                             stego_path=stego_path,
                             payload=payload)
    except json.JSONDecodeError as e:
        flash(f'Invalid JSON in steganographic data: {str(e)}', 'error')
        return redirect(url_for('admin_panel'))
    except Exception as e:
        flash(f'Error reading steganographic data: {str(e)}', 'error')
        return redirect(url_for('admin_panel'))

@app.route('/profile/generate', methods=['POST'])
@login_required
def generate_profile_image():
    """Generate a new profile image while preserving encryption keys."""
    try:
        user = User.query.get(current_user.id)
        
        # Get existing keys and indexes if they exist
        existing_keys = {}
        existing_index = {}
        
        if user.stego_image and os.path.exists(user.stego_image):
            try:
                hidden_data = lsb.reveal(user.stego_image)
                if hidden_data:
                    payload = json.loads(hidden_data)
                    existing_keys = payload.get('keys', {})
                    existing_index = payload.get('index', {})
            except Exception as e:
                logger.warning(f"Could not extract existing steganographic data: {e}")
                existing_keys = {}
                existing_index = {}
        
        # Generate new profile image
        from PIL import Image, ImageDraw
        import random
        
        # Create a colorful gradient profile image
        img = Image.new('RGB', (300, 300), color='white')
        draw = ImageDraw.Draw(img)
        
        # Create gradient background
        for y in range(300):
            color = (random.randint(100, 255), random.randint(100, 255), random.randint(100, 255))
            draw.line([(0, y), (300, y)], fill=color)
        
        # Add some geometric shapes
        draw.ellipse([50, 50, 250, 250], outline=(255, 255, 255), width=3)
        draw.rectangle([100, 100, 200, 200], outline=(255, 255, 255), width=2)
        
        # Save new profile image
        new_profile_path = f"profile_user_{user.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
        img.save(new_profile_path)
        
        # Update user's plain profile image (server-side)
        user.profile_image = new_profile_path
        
        # Note: Steganographic image with keys remains client-side only
        # The stego_image field is not updated to keep it client-side
        payload = {
            "user_id": user.id,
            "index": existing_index,
            "keys": existing_keys,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            payload_str = json.dumps(payload)
            stego_image = lsb.hide(new_profile_path, payload_str)
        except Exception as e:
            logger.error(f"Error creating steganographic image: {e}")
            # Fallback: just save the profile image without steganography
            user.stego_image = new_profile_path
            db.session.commit()
            return
        
        # Save stego image
        stego_path = f"stego_user_{user.id}.png"
        stego_image.save(stego_path)
        
        # Update user record
        user.stego_image = stego_path
        db.session.commit()
        
        log_activity(user.id, 'profile_generate', success=True)
        flash('New profile image generated successfully!', 'success')
        
    except Exception as e:
        logger.error(f"Profile generation error: {e}")
        log_activity(current_user.id, 'profile_generate', success=False, details=str(e))
        flash(f'Error generating profile image: {str(e)}', 'error')
    
    return redirect(url_for('profile'))

@app.route('/profile/upload', methods=['POST'])
@login_required
def upload_profile_image():
    """Upload a custom profile image while preserving encryption keys."""
    try:
        if 'profile_image' not in request.files:
            flash('No image selected', 'error')
            return redirect(url_for('profile'))
        
        file = request.files['profile_image']
        if file.filename == '':
            flash('No image selected', 'error')
            return redirect(url_for('profile'))
        
        if file:
            user = User.query.get(current_user.id)
            
            # Get existing keys and indexes if they exist
            existing_keys = {}
            existing_index = {}
            
            if user.stego_image and os.path.exists(user.stego_image):
                try:
                    hidden_data = lsb.reveal(user.stego_image)
                    if hidden_data:
                        payload = json.loads(hidden_data)
                        existing_keys = payload.get('keys', {})
                        existing_index = payload.get('index', {})
                except Exception as e:
                    logger.warning(f"Could not extract existing steganographic data: {e}")
                    existing_keys = {}
                    existing_index = {}
            
            # Save uploaded image
            filename = secure_filename(file.filename)
            new_profile_path = f"profile_user_{user.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{filename}"
            file.save(new_profile_path)
            
            # Update user's plain profile image (server-side)
            user.profile_image = new_profile_path
            
            # Note: Steganographic image with keys remains client-side only
            # The stego_image field is not updated to keep it client-side
            payload = {
                "user_id": user.id,
                "index": existing_index,
                "keys": existing_keys,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            try:
                payload_str = json.dumps(payload)
                stego_image = lsb.hide(new_profile_path, payload_str)
            except Exception as e:
                logger.error(f"Error creating steganographic image: {e}")
                # Fallback: just save the profile image without steganography
                user.stego_image = new_profile_path
                db.session.commit()
                return
            
            # Save stego image
            stego_path = f"stego_user_{user.id}.png"
            stego_image.save(stego_path)
            
            # Update user record
            user.stego_image = stego_path
            db.session.commit()
            
            log_activity(user.id, 'profile_upload', success=True)
            flash('Profile image uploaded successfully!', 'success')
        
    except Exception as e:
        logger.error(f"Profile upload error: {e}")
        log_activity(current_user.id, 'profile_upload', success=False, details=str(e))
        flash(f'Error uploading profile image: {str(e)}', 'error')
    
    return redirect(url_for('profile'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Create admin user if none exists
        if not User.query.filter_by(user_level='admin').first():
            admin = User(
                username='admin',
                email='admin@enccloudstorage.com',
                password_hash=generate_password_hash('admin123'),
                user_level='admin'
            )
            db.session.add(admin)
            db.session.commit()
            logger.info("Default admin user created (username: admin, password: admin123)")
    
    app.run(debug=True)
