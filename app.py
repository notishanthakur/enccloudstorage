from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import json
import hashlib
import logging
import random
from datetime import datetime, timedelta
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
import PyPDF2
import docx
import openpyxl
from pptx import Presentation
import fitz  # PyMuPDF

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

def extract_file_content(file_path: str, filename: str) -> str:
    """Extract text content from various file types."""
    try:
        file_ext = filename.lower().split('.')[-1]
        content = ""
        
        if file_ext == 'pdf':
            # Method 1: PyPDF2
            try:
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    for page in pdf_reader.pages:
                        content += page.extract_text() + " "
            except:
                # Method 2: PyMuPDF (fitz) - more reliable
                try:
                    doc = fitz.open(file_path)
                    for page in doc:
                        content += page.get_text() + " "
                    doc.close()
                except:
                    pass
        
        elif file_ext == 'docx':
            try:
                doc = docx.Document(file_path)
                for paragraph in doc.paragraphs:
                    content += paragraph.text + " "
            except:
                pass
        
        elif file_ext in ['xlsx', 'xls']:
            try:
                workbook = openpyxl.load_workbook(file_path)
                for sheet_name in workbook.sheetnames:
                    sheet = workbook[sheet_name]
                    for row in sheet.iter_rows():
                        for cell in row:
                            if cell.value:
                                content += str(cell.value) + " "
            except:
                pass
        
        elif file_ext == 'pptx':
            try:
                prs = Presentation(file_path)
                for slide in prs.slides:
                    for shape in slide.shapes:
                        if hasattr(shape, "text"):
                            content += shape.text + " "
            except:
                pass
        
        elif file_ext in ['txt', 'md', 'csv']:
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()
            except:
                try:
                    with open(file_path, 'r', encoding='latin-1') as file:
                        content = file.read()
                except:
                    pass
        
        return content.strip()
        
    except Exception as e:
        logger.error(f"Error extracting content from {filename}: {str(e)}")
        return ""

def extract_keywords(text: str) -> list:
    """Extract keywords from text with advanced NLP processing."""
    import re
    import string
    
    # Convert to lowercase and clean text
    text = text.lower()
    
    # Remove special characters but keep spaces and hyphens
    text = re.sub(r'[^\w\s\-]', ' ', text)
    
    # Split into words
    words = text.split()
    
    # Enhanced stopwords list
    stopwords = {
        "the", "a", "an", "is", "and", "of", "to", "in", "for", "with", "on", "at", "by", "from", "up", "about", "into", "through", "during", "before", "after", "above", "below", "between", "among",
        "this", "that", "these", "those", "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us", "them",
        "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "can", "must",
        "be", "been", "being", "am", "are", "was", "were", "get", "got", "make", "made", "take", "took", "come", "came",
        "go", "went", "see", "saw", "know", "knew", "think", "thought", "say", "said", "tell", "told", "want", "wanted",
        "need", "needed", "use", "used", "work", "worked", "call", "called", "try", "tried", "ask", "asked", "feel", "felt",
        "also", "just", "like", "more", "most", "other", "some", "very", "when", "where", "why", "how", "what", "who",
        "all", "any", "both", "each", "few", "many", "much", "several", "such", "only", "own", "same", "than", "too",
        "here", "there", "now", "then", "well", "back", "down", "off", "over", "under", "again", "further", "once"
    }
    
    # Extract meaningful keywords
    keywords = []
    for word in words:
        word = word.strip()
        if len(word) > 2 and word not in stopwords and word.isalpha():
            keywords.append(word)
    
    # Add variations for better search matching
    enhanced_keywords = []
    for keyword in keywords:
        enhanced_keywords.append(keyword)
        
        # Add plural/singular variations
        if keyword.endswith('s') and len(keyword) > 3:
            enhanced_keywords.append(keyword[:-1])  # Remove 's'
        elif not keyword.endswith('s'):
            enhanced_keywords.append(keyword + 's')  # Add 's'
        
        # Add common variations
        if keyword.endswith('ing'):
            enhanced_keywords.append(keyword[:-3])  # Remove 'ing'
        if keyword.endswith('ed'):
            enhanced_keywords.append(keyword[:-2])  # Remove 'ed'
        if keyword.endswith('er'):
            enhanced_keywords.append(keyword[:-2])  # Remove 'er'
        if keyword.endswith('ly'):
            enhanced_keywords.append(keyword[:-2])  # Remove 'ly'
        if keyword.endswith('tion'):
            enhanced_keywords.append(keyword[:-4])  # Remove 'tion'
        if keyword.endswith('sion'):
            enhanced_keywords.append(keyword[:-4])  # Remove 'sion'
    
    # Remove duplicates while preserving order
    seen = set()
    unique_keywords = []
    for keyword in enhanced_keywords:
        if keyword not in seen:
            seen.add(keyword)
            unique_keywords.append(keyword)
    
    return unique_keywords

def analyze_binary_file_content(file_data: bytes, filename: str) -> str:
    """Analyze binary file content to extract metadata and text."""
    import struct
    
    text_content = ""
    
    try:
        # Try to extract text from common binary formats
        if filename.lower().endswith('.pdf'):
            # Basic PDF text extraction (simplified)
            pdf_text = file_data.decode('latin-1', errors='ignore')
            # Extract text between BT and ET markers (PDF text objects)
            import re
            text_objects = re.findall(r'BT\s+(.*?)\s+ET', pdf_text, re.DOTALL)
            for obj in text_objects:
                # Extract text content from PDF objects
                text_matches = re.findall(r'\((.*?)\)', obj)
                text_content += ' '.join(text_matches) + ' '
        
        elif filename.lower().endswith(('.doc', '.docx')):
            # Basic DOC/DOCX text extraction
            doc_text = file_data.decode('latin-1', errors='ignore')
            # Extract readable text (basic approach)
            import re
            readable_text = re.findall(r'[a-zA-Z]{3,}', doc_text)
            text_content += ' '.join(readable_text) + ' '
        
        elif filename.lower().endswith(('.xls', '.xlsx')):
            # Basic Excel text extraction
            xls_text = file_data.decode('latin-1', errors='ignore')
            import re
            readable_text = re.findall(r'[a-zA-Z]{3,}', xls_text)
            text_content += ' '.join(readable_text) + ' '
        
        elif filename.lower().endswith(('.ppt', '.pptx')):
            # Basic PowerPoint text extraction
            ppt_text = file_data.decode('latin-1', errors='ignore')
            import re
            readable_text = re.findall(r'[a-zA-Z]{3,}', ppt_text)
            text_content += ' '.join(readable_text) + ' '
        
        # For image files, try to extract EXIF data
        elif filename.lower().endswith(('.jpg', '.jpeg', '.png', '.tiff')):
            try:
                from PIL import Image
                from PIL.ExifTags import TAGS
                import io
                
                image = Image.open(io.BytesIO(file_data))
                exif_data = image._getexif()
                if exif_data:
                    for tag_id, value in exif_data.items():
                        tag = TAGS.get(tag_id, tag_id)
                        if isinstance(value, str):
                            text_content += value + ' '
            except:
                pass
        
        # For any binary file, try to extract readable strings
        if not text_content:
            # Extract ASCII strings from binary data
            import re
            ascii_strings = re.findall(rb'[\x20-\x7E]{4,}', file_data)
            for string in ascii_strings:
                try:
                    text_content += string.decode('ascii') + ' '
                except:
                    pass
    
    except Exception as e:
        logger.warning(f"Error analyzing binary file content: {e}")
    
    return text_content

def extract_nlp_keywords(text: str, filename: str = "") -> list:
    """Advanced NLP-based keyword extraction with multiple techniques."""
    import re
    import string
    from collections import Counter
    
    all_keywords = []
    
    # 1. Basic keyword extraction
    basic_keywords = extract_keywords(text)
    all_keywords.extend(basic_keywords)
    
    # 2. Extract from filename
    if filename:
        filename_keywords = extract_keywords(filename)
        all_keywords.extend(filename_keywords)
    
    # 3. N-gram extraction (bigrams and trigrams)
    words = text.lower().split()
    for n in [2, 3]:
        for i in range(len(words) - n + 1):
            ngram = ' '.join(words[i:i+n])
            # Clean ngram
            ngram = re.sub(r'[^\w\s]', '', ngram).strip()
            if len(ngram) > 3 and ' ' in ngram:
                all_keywords.append(ngram)
    
    # 4. Extract compound words and phrases
    compound_patterns = [
        r'\b\w+-\w+\b',  # hyphenated words
        r'\b\w+\s+\w+\b',  # two-word phrases
        r'\b\w+\s+\w+\s+\w+\b',  # three-word phrases
    ]
    
    for pattern in compound_patterns:
        matches = re.findall(pattern, text.lower())
        for match in matches:
            clean_match = re.sub(r'[^\w\s\-]', '', match).strip()
            if len(clean_match) > 3:
                all_keywords.append(clean_match)
    
    # 5. Extract technical terms and acronyms
    acronym_pattern = r'\b[A-Z]{2,}\b'
    acronyms = re.findall(acronym_pattern, text)
    all_keywords.extend([acronym.lower() for acronym in acronyms])
    
    # 6. Extract numbers and dates
    number_patterns = [
        r'\b\d{4}\b',  # years
        r'\b\d{1,2}/\d{1,2}/\d{4}\b',  # dates
        r'\b\d+%\b',  # percentages
        r'\b\d+\.\d+\b',  # decimals
    ]
    
    for pattern in number_patterns:
        matches = re.findall(pattern, text)
        all_keywords.extend(matches)
    
    # 7. Extract domain-specific terms
    domain_terms = [
        # Technical terms
        'api', 'database', 'server', 'client', 'protocol', 'algorithm', 'encryption', 'security',
        'authentication', 'authorization', 'session', 'cookie', 'token', 'password', 'username',
        'email', 'phone', 'address', 'contact', 'profile', 'account', 'user', 'admin',
        # Business terms
        'budget', 'cost', 'price', 'revenue', 'profit', 'loss', 'investment', 'market',
        'customer', 'client', 'vendor', 'supplier', 'partner', 'contract', 'agreement',
        # Document terms
        'report', 'analysis', 'summary', 'conclusion', 'recommendation', 'proposal',
        'meeting', 'conference', 'presentation', 'document', 'file', 'folder', 'directory',
        # Time-related terms
        'today', 'yesterday', 'tomorrow', 'week', 'month', 'year', 'quarter', 'annual',
        'daily', 'weekly', 'monthly', 'quarterly', 'deadline', 'schedule', 'timeline',
        # Status terms
        'active', 'inactive', 'pending', 'completed', 'failed', 'success', 'error',
        'approved', 'rejected', 'draft', 'final', 'version', 'update', 'revision'
    ]
    
    # Check if any domain terms appear in text
    text_lower = text.lower()
    for term in domain_terms:
        if term in text_lower:
            all_keywords.append(term)
    
    # 8. Extract semantic variations
    semantic_groups = {
        'data': ['information', 'content', 'details', 'facts', 'records', 'files'],
        'system': ['platform', 'application', 'software', 'program', 'tool'],
        'user': ['person', 'individual', 'customer', 'client', 'member'],
        'file': ['document', 'record', 'data', 'content', 'information'],
        'security': ['protection', 'safety', 'privacy', 'confidentiality'],
        'time': ['date', 'schedule', 'timeline', 'duration', 'period'],
        'status': ['state', 'condition', 'situation', 'position', 'level']
    }
    
    for group, synonyms in semantic_groups.items():
        if any(syn in text_lower for syn in synonyms):
            all_keywords.append(group)
            all_keywords.extend(synonyms)
    
    # 9. Extract file-specific metadata
    if filename:
        # Extract file extension
        if '.' in filename:
            ext = filename.split('.')[-1].lower()
            all_keywords.append(ext)
        
        # Extract path components
        path_parts = filename.replace('\\', '/').split('/')
        for part in path_parts:
            if part and '.' not in part:  # Skip file extensions
                clean_part = re.sub(r'[^\w]', '', part).lower()
                if len(clean_part) > 2:
                    all_keywords.append(clean_part)
    
    # 10. Add contextual keywords based on content analysis
    content_indicators = {
        'technical': ['code', 'programming', 'development', 'software', 'system', 'api', 'database'],
        'business': ['report', 'analysis', 'meeting', 'proposal', 'budget', 'revenue', 'customer'],
        'personal': ['profile', 'contact', 'address', 'phone', 'email', 'family', 'friend'],
        'academic': ['research', 'study', 'paper', 'thesis', 'analysis', 'experiment', 'data'],
        'medical': ['patient', 'treatment', 'diagnosis', 'medical', 'health', 'doctor', 'hospital'],
        'legal': ['contract', 'agreement', 'legal', 'law', 'court', 'document', 'clause']
    }
    
    for category, indicators in content_indicators.items():
        if any(indicator in text_lower for indicator in indicators):
            all_keywords.append(category)
            all_keywords.extend(indicators)
    
    # 11. Frequency-based keyword extraction
    word_freq = Counter([word for word in text.lower().split() if len(word) > 3])
    frequent_words = [word for word, count in word_freq.most_common(10) if count > 1]
    all_keywords.extend(frequent_words)
    
    # 12. Add timestamp-based keywords
    from datetime import datetime
    now = datetime.utcnow()
    time_keywords = [
        now.strftime('%Y'),
        now.strftime('%m'),
        now.strftime('%B').lower(),
        now.strftime('%A').lower(),
        now.strftime('%Y-%m'),
        now.strftime('%Y-%m-%d')
    ]
    all_keywords.extend(time_keywords)
    
    # Clean and deduplicate
    cleaned_keywords = []
    seen = set()
    for keyword in all_keywords:
        keyword = keyword.strip().lower()
        if (keyword and 
            len(keyword) > 1 and 
            keyword not in seen and 
            not keyword.isdigit() and  # Skip pure numbers
            len(keyword) < 50):  # Skip very long strings
            seen.add(keyword)
            cleaned_keywords.append(keyword)
    
    return cleaned_keywords

def hash_keyword(word: str) -> str:
    """Hash keyword with SHA-256."""
    return hashlib.sha256(word.encode()).hexdigest()

def generate_search_variations(search_term: str) -> list:
    """Generate multiple variations of search terms for better matching."""
    variations = []
    search_term_lower = search_term.lower()
    
    # Add original term
    variations.append(search_term_lower)
    
    # Extract keywords from search term
    keywords = extract_keywords(search_term)
    variations.extend(keywords)
    
    # Add partial matches (substrings)
    words = search_term_lower.split()
    for word in words:
        if len(word) > 3:
            # Add first 3+ characters
            for i in range(3, len(word)):
                variations.append(word[:i])
    
    # Add common typos/variations
    for keyword in keywords:
        if len(keyword) > 4:
            # Remove last character (common typo)
            variations.append(keyword[:-1])
            # Add common letter substitutions
            variations.append(keyword.replace('c', 'k'))
            variations.append(keyword.replace('k', 'c'))
            variations.append(keyword.replace('ph', 'f'))
            variations.append(keyword.replace('f', 'ph'))
    
    # Remove duplicates and empty strings
    unique_variations = []
    seen = set()
    for variation in variations:
        variation = variation.strip()
        if variation and len(variation) > 1 and variation not in seen:
            seen.add(variation)
            unique_variations.append(variation)
    
    return unique_variations

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
                
                # Extract keywords from file content and filename
                keywords = []
                
                # Always extract keywords from filename
                filename_keywords = extract_keywords(original_filename)
                keywords.extend(filename_keywords)
                
                # Save file temporarily to extract content
                temp_file_path = f"temp_{original_filename}"
                with open(temp_file_path, 'wb') as temp_file:
                    temp_file.write(file_data)
                
                try:
                    # Extract content from file
                    file_content = extract_file_content(temp_file_path, original_filename)
                    if file_content:
                        content_keywords = extract_keywords(file_content)
                        keywords.extend(content_keywords)
                        logger.info(f"Extracted {len(content_keywords)} keywords from file content")
                    else:
                        logger.info("No content extracted from file")
                except Exception as e:
                    logger.error(f"Error extracting content: {str(e)}")
                finally:
                    # Clean up temp file
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
                
                # Add file type keywords for better searchability
                file_ext = original_filename.lower().split('.')[-1]
                if file_ext in ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx']:
                    keywords.extend([file_ext, 'document', 'file'])
                elif file_ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg']:
                    keywords.extend(['image', 'picture', 'photo', 'graphic'])
                elif file_ext in ['mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv']:
                    keywords.extend(['video', 'movie', 'clip', 'recording'])
                elif file_ext in ['mp3', 'wav', 'flac', 'aac', 'ogg']:
                    keywords.extend(['audio', 'music', 'sound', 'recording'])
                elif file_ext in ['zip', 'rar', '7z', 'tar', 'gz']:
                    keywords.extend(['archive', 'compressed', 'zip', 'backup'])
                
                # Add common file-related keywords
                keywords.extend(['file', 'document', 'data'])
                
                # Add timestamp-based keywords
                current_time = datetime.utcnow()
                keywords.extend([
                    current_time.strftime('%Y'),
                    current_time.strftime('%m'),
                    current_time.strftime('%B').lower(),  # month name
                    current_time.strftime('%A').lower()   # day name
                ])
                
                # Remove duplicates while preserving order and limit keywords
                unique_keywords = []
                seen = set()
                for keyword in keywords:
                    keyword = keyword.strip().lower()
                    if (keyword and 
                        keyword not in seen and 
                        len(keyword) > 2 and 
                        len(unique_keywords) < 20):  # Limit to 20 keywords per file
                        seen.add(keyword)
                        unique_keywords.append(keyword)
                
                # Create keyword hash map
                keyword_hashes = {hash_keyword(kw): True for kw in unique_keywords}
                
                # Log keyword generation for debugging
                logger.info(f"Generated {len(unique_keywords)} keywords for file '{original_filename}': {unique_keywords[:10]}...")  # Show first 10 keywords
                
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
                try:
                    update_stego_image(current_user.id)
                    logger.info(f"Steganographic image updated for user {current_user.id}")
                except Exception as e:
                    logger.error(f"Failed to update stego image for user {current_user.id}: {e}")
                    # Don't fail the upload if stego image creation fails
                    pass
                
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
                # Only add if not already mapped to avoid overwriting
                if keyword_hash not in master_index:
                    master_index[keyword_hash] = file_record.blob_name
                else:
                    # If already mapped, create a list of files for this keyword
                    if isinstance(master_index[keyword_hash], list):
                        if file_record.blob_name not in master_index[keyword_hash]:
                            master_index[keyword_hash].append(file_record.blob_name)
                    else:
                        # Convert to list if it's a single file
                        existing_file = master_index[keyword_hash]
                        if existing_file != file_record.blob_name:
                            master_index[keyword_hash] = [existing_file, file_record.blob_name]
            
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
                img = Image.new('RGB', (400, 400), color='lightblue')
                img.save(profile_img_path)
            except ImportError:
                return
        
        # Embed data in image
        try:
            payload_str = json.dumps(payload)
            stego_image = lsb.hide(profile_img_path, payload_str)
        except Exception as e:
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
        
    except Exception as e:
        pass

@app.route('/search', methods=['GET', 'POST'])
@login_required
def search_files():
    if request.method == 'POST':
        search_term = request.form.get('search_term', '').strip()
        if not search_term:
            flash('Please enter a search term', 'error')
            return render_template('search.html')
        
        try:
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
            
            # Simple and accurate search algorithm
            matches = []
            search_index = payload.get('index', {})
            
            # Extract simple keywords from search term
            search_keywords = extract_keywords(search_term)
            
            # If no keywords extracted, use the original term
            if not search_keywords:
                search_keywords = [search_term.lower()]
            
            # Search for each keyword
            found_files = set()
            for keyword in search_keywords:
                keyword_hash = hash_keyword(keyword)
                
                # Exact match in index
                if keyword_hash in search_index:
                    blob_name = search_index[keyword_hash]
                    # Handle both single file and list of files
                    if isinstance(blob_name, list):
                        found_files.update(blob_name)
                    else:
                        found_files.add(blob_name)
            
            # Get file records for found blobs
            for blob_name in found_files:
                file_record = File.query.filter_by(blob_name=blob_name, user_id=current_user.id).first()
                if file_record:
                    matches.append({
                        'id': file_record.id,
                        'filename': file_record.original_filename,
                        'upload_date': file_record.upload_date,
                        'file_size': file_record.file_size
                    })
            
            # If no exact matches found, try filename search
            if not matches:
                # Get all user files and search in filenames
                user_files = File.query.filter_by(user_id=current_user.id).all()
                for file_record in user_files:
                    filename_lower = file_record.original_filename.lower()
                    # Check if any search keyword is in filename
                    for keyword in search_keywords:
                        if keyword in filename_lower:
                            matches.append({
                                'id': file_record.id,
                                'filename': file_record.original_filename,
                                'upload_date': file_record.upload_date,
                                'file_size': file_record.file_size
                            })
                            break  # Avoid duplicates
            
            # Remove duplicates based on file ID
            unique_matches = []
            seen_ids = set()
            for match in matches:
                if match['id'] not in seen_ids:
                    unique_matches.append(match)
                    seen_ids.add(match['id'])
            
            log_activity(current_user.id, 'search', resource=search_term, success=True, details=f"Found {len(unique_matches)} matches")
            
            return render_template('search.html', matches=unique_matches, search_term=search_term)
            
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




@app.route('/debug/search-index')
@login_required
def debug_search_index():
    """Debug route to check search index contents."""
    try:
        user = User.query.get(current_user.id)
        if not user.stego_image or not os.path.exists(user.stego_image):
            return jsonify({'error': 'No stego image found'})
        
        hidden_payload = lsb.reveal(user.stego_image)
        if not hidden_payload:
            return jsonify({'error': 'No hidden data found'})
        
        payload = json.loads(hidden_payload)
        search_index = payload.get('index', {})
        keys = payload.get('keys', {})
        
        # Show first 10 index entries
        index_sample = dict(list(search_index.items())[:10])
        
        return jsonify({
            'total_index_entries': len(search_index),
            'total_keys': len(keys),
            'index_sample': index_sample,
            'user_id': payload.get('user_id'),
            'timestamp': payload.get('timestamp')
        })
        
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/debug/regenerate-stego')
@login_required
def debug_regenerate_stego():
    """Regenerate steganographic image with fixed algorithm."""
    try:
        user_id = current_user.id
        logger.info(f"Regenerating stego image for user {user_id}")
        
        # Force update steganographic image
        update_stego_image(user_id)
        
        # Check if it was created
        user = User.query.get(user_id)
        if user.stego_image and os.path.exists(user.stego_image):
            return jsonify({
                'success': True,
                'message': 'Steganographic image regenerated successfully',
                'stego_path': user.stego_image
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to regenerate steganographic image'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/debug/unhash-keywords')
@login_required
def debug_unhash_keywords():
    """Unhash keywords to see what they actually are."""
    try:
        user = User.query.get(current_user.id)
        if not user.stego_image or not os.path.exists(user.stego_image):
            return jsonify({'error': 'No stego image found'})
        
        hidden_payload = lsb.reveal(user.stego_image)
        if not hidden_payload:
            return jsonify({'error': 'No hidden data found'})
        
        payload = json.loads(hidden_payload)
        search_index = payload.get('index', {})
        
        # Try to reverse engineer keywords from common words
        common_keywords = [
            'pdf', 'document', 'file', 'text', 'data', 'content', 'information',
            'report', 'analysis', 'study', 'research', 'paper', 'article',
            'image', 'photo', 'picture', 'graphic', 'visual', 'media',
            'esd', 'ia3', 'assignment', 'homework', 'project', 'task',
            '2025', 'january', 'february', 'march', 'april', 'may', 'june',
            'july', 'august', 'september', 'october', 'november', 'december',
            'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
            'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
            'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'
        ]
        
        # Test each common keyword to see which hashes match
        matched_keywords = {}
        for keyword in common_keywords:
            keyword_hash = hashlib.sha256(keyword.encode()).hexdigest()
            if keyword_hash in search_index:
                matched_keywords[keyword] = search_index[keyword_hash]
        
        # Also try to get all files and their keywords from database
        user_files = File.query.filter_by(user_id=current_user.id).all()
        file_keywords = {}
        
        for file_record in user_files:
            try:
                keywords_data = json.loads(file_record.keywords_hash)
                file_keywords[file_record.filename] = list(keywords_data.keys())
            except:
                file_keywords[file_record.filename] = []
        
        # Try to unhash the specific hashes you provided
        your_hashes = [
            "1a79668eac4051a9128b81c116007d1b41ce17828d7722afc9746699f4e817b8",
            "3a6eb0790f39ac87c94f3856b2dd2c5d110e6811602261a9a923d3bb23adc8b7",
            "3b9c358f36f0a31b6ad3e14f309c7cf198ac9246e8316f9ce543d5b19ac02b80",
            "43cc23fa52b87b4cc1d02b5b114154151d6adddb17c9fddc06b027fa99e24008",
            "4a44dc15364204a80fe80e9039455cc1608281820fe2b24f1e5233ade6af1dd5",
            "7aee5b5dbb9e781589946f9087eb09e4a880d57e5d52441daaf7d49f9c2e629f",
            "b0ce975f9314b741951b9ad9b586f3784428146ed765a041696d0e98bd56ce5d",
            "b2b2f104d32c638903e151a9a923d3bb23adc8b7",
            "c35b21d6ca39aa7cc3b79a705d989f1a6e88b99ab43988d74048799e3db926a3"
        ]
        
        # Extended keyword list for your specific case
        extended_keywords = [
            'esd', 'ia3', 'pdf', 'document', 'assignment', 'homework', 'project',
            '2025', 'january', 'feb', 'jan', 'october', 'oct', 'november', 'nov',
            'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
            'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun',
            'file', 'text', 'data', 'content', 'information', 'report', 'analysis',
            'study', 'research', 'paper', 'article', 'task', 'work', 'academic',
            'student', 'education', 'learning', 'course', 'subject', 'topic',
            'digital', 'electronic', 'computer', 'technology', 'system', 'design',
            'engineering', 'software', 'hardware', 'programming', 'development',
            'application', 'interface', 'user', 'experience', 'interaction',
            'security', 'encryption', 'privacy', 'protection', 'safety',
            'storage', 'database', 'management', 'administration', 'control',
            'network', 'communication', 'protocol', 'standard', 'specification',
            'implementation', 'algorithm', 'method', 'technique', 'approach',
            'solution', 'problem', 'challenge', 'requirement', 'specification',
            'testing', 'validation', 'verification', 'quality', 'performance',
            'optimization', 'efficiency', 'effectiveness', 'reliability', 'stability'
        ]
        
        unhashed_results = {}
        for keyword in extended_keywords:
            keyword_hash = hashlib.sha256(keyword.encode()).hexdigest()
            if keyword_hash in your_hashes:
                unhashed_results[keyword] = keyword_hash
        
        return jsonify({
            'total_index_entries': len(search_index),
            'matched_common_keywords': matched_keywords,
            'file_keywords': file_keywords,
            'unhashed_your_keywords': unhashed_results,
            'your_hashes_found': [h for h in your_hashes if h in search_index],
            'sample_hashes': dict(list(search_index.items())[:5]),
            'message': 'Check unhashed_your_keywords to see what your specific keywords are'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)})

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

def add_backdated_logs():
    """Add backdated logs for the past week."""
    with app.app_context():
        # Get all existing users
        users = User.query.all()
        
        if not users:
            print("No users found in database. Please create users first.")
            return
        
        print(f"Found {len(users)} users:")
        for user in users:
            print(f"  - ID: {user.id}, Username: {user.username}, Level: {user.user_level}")
        
        # Define possible actions and resources
        actions = ['login', 'logout', 'upload', 'download', 'search', 'decrypt', 'profile_update']
        file_types = ['document.pdf', 'image.jpg', 'spreadsheet.xlsx', 'presentation.pptx', 'text.txt', 'data.csv']
        search_terms = ['project', 'report', 'meeting', 'budget', 'analysis', 'data', 'research', 'notes']
        
        # Generate logs for the past 7 days
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)
        
        logs_added = 0
        
        for day in range(7):
            current_date = start_date + timedelta(days=day)
            
            # Generate 5-15 logs per day
            num_logs = random.randint(5, 15)
            
            for _ in range(num_logs):
                # Select random user
                user = random.choice(users)
                
                # Select random action
                action = random.choice(actions)
                
                # Generate resource based on action
                resource = None
                if action == 'upload':
                    resource = random.choice(file_types)
                elif action == 'search':
                    resource = random.choice(search_terms)
                elif action == 'download':
                    resource = random.choice(file_types)
                elif action == 'decrypt':
                    resource = random.choice(file_types)
                
                # Generate random time within the day
                random_hour = random.randint(0, 23)
                random_minute = random.randint(0, 59)
                random_second = random.randint(0, 59)
                
                log_timestamp = current_date.replace(
                    hour=random_hour,
                    minute=random_minute,
                    second=random_second
                )
                
                # Generate random IP addresses
                ip_addresses = [
                    '192.168.1.100', '192.168.1.101', '192.168.1.102',
                    '10.0.0.50', '10.0.0.51', '172.16.0.10',
                    '203.0.113.1', '198.51.100.1'
                ]
                
                # Generate random user agents
                user_agents = [
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15'
                ]
                
                # 90% success rate
                success = random.random() < 0.9
                
                # Generate details for some actions
                details = None
                if action == 'upload' and success:
                    details = f"File size: {random.randint(100, 5000)}KB, Encryption: AES-256"
                elif action == 'search' and success:
                    details = f"Found {random.randint(1, 10)} results"
                elif action == 'decrypt' and success:
                    details = f"Decryption successful, Key source: steganographic"
                elif not success:
                    details = random.choice([
                        "Authentication failed",
                        "File not found",
                        "Permission denied",
                        "Network timeout",
                        "Invalid file format"
                    ])
                
                # Create log entry
                log_entry = ActivityLog(
                    user_id=user.id,
                    action=action,
                    resource=resource,
                    ip_address=random.choice(ip_addresses),
                    user_agent=random.choice(user_agents),
                    timestamp=log_timestamp,
                    success=success,
                    details=details
                )
                
                db.session.add(log_entry)
                logs_added += 1
        
        # Commit all logs
        try:
            db.session.commit()
            print(f"\nSuccessfully added {logs_added} backdated logs spanning 7 days!")
            print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
            
            # Show some statistics
            total_logs = ActivityLog.query.count()
            print(f"Total logs in database: {total_logs}")
            
            # Show logs by action
            print("\nLogs by action:")
            from sqlalchemy import func
            action_counts = db.session.query(
                ActivityLog.action, 
                func.count(ActivityLog.id)
            ).group_by(ActivityLog.action).all()
            
            for action, count in action_counts:
                print(f"  - {action}: {count}")
                
        except Exception as e:
            db.session.rollback()
            print(f"Error adding logs: {e}")

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
        
        # Add backdated logs if requested
        import sys
        if len(sys.argv) > 1 and sys.argv[1] == '--add-logs':
            add_backdated_logs()
    
    app.run(debug=True)
