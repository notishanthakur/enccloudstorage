# EncCloudStorage Web Application

A privacy-preserving cloud storage system with searchable encryption and steganographic key management, now converted to a modern web application.

## 🚀 Features

### Core Security Features
- **AES-256 Encryption**: All files encrypted before upload
- **Searchable Encryption**: Search encrypted files without revealing content
- **Steganographic Key Storage**: Keys hidden in profile pictures
- **Zero-Knowledge Architecture**: Server never sees unencrypted data

### Web Application Features
- **Modern Web Interface**: Responsive Bootstrap-based UI
- **User Authentication**: Secure login/registration system
- **Two User Levels**: Admin and regular user access controls
- **File Management**: Upload, download, and search encrypted files
- **Activity Logging**: Comprehensive audit trail
- **Azure Blob Storage**: Cloud storage integration
- **Database Integration**: SQLAlchemy with PostgreSQL/SQLite support

## 🏗️ Architecture

### Technology Stack
- **Backend**: Flask (Python)
- **Database**: PostgreSQL (production) / SQLite (development)
- **Storage**: Azure Blob Storage
- **Frontend**: Bootstrap 5, HTML5, CSS3, JavaScript
- **Security**: PyCryptodome, Stegano
- **Deployment**: Docker, Docker Compose

### Security Architecture
```
User File → AES-256 Encryption → Azure Blob Storage
     ↓
Keywords → SHA-256 Hash → Encrypted Index
     ↓
Keys + Index → Steganography → Profile Picture
```

## 📦 Installation

### Prerequisites
- Python 3.8+
- PostgreSQL (for production)
- Azure Storage Account (optional)
- Docker (for containerized deployment)

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/notishanthakur/enccloudstorage
   cd enccloudstorage
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Initialize database**
   ```bash
   python run.py
   ```

5. **Run the application**
   ```bash
   python run.py
   ```

### Docker Deployment

1. **Build and run with Docker Compose**
   ```bash
   docker-compose up -d
   ```

2. **Access the application**
   - Web interface: http://localhost:5000
   - Default admin: username `admin`, password `admin123`

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key | `dev-secret-key-change-in-production` |
| `DATABASE_URL` | Database connection string | `sqlite:///enccloudstorage.db` |
| `AZURE_STORAGE_ACCOUNT_NAME` | Azure storage account name | Required for cloud storage |
| `AZURE_STORAGE_CONTAINER_NAME` | Azure container name | `enccloudstorage` |
| `AZURE_STORAGE_ACCOUNT_KEY` | Azure storage key | Optional (uses managed identity) |
| `FLASK_ENV` | Environment (development/production) | `development` |

### Database Configuration

#### SQLite (Development)
```python
DATABASE_URL = "sqlite:///enccloudstorage.db"
```

#### PostgreSQL (Production)
```python
DATABASE_URL = "postgresql://username:password@localhost/enccloudstorage"
```

#### MySQL
```python
DATABASE_URL = "mysql://username:password@localhost/enccloudstorage"
```

## 🎯 Usage

### User Workflow

1. **Registration/Login**
   - Register new account or login with existing credentials
   - Admin users have additional management capabilities

2. **File Upload**
   - Select file to upload
   - Choose access level (private/shared/public)
   - File is automatically encrypted and uploaded

3. **File Search**
   - Search through encrypted files using keywords
   - Search terms are hashed locally for privacy
   - Results show matching files without revealing content

4. **File Download**
   - Download and decrypt files using keys from profile picture
   - All decryption happens client-side

### Admin Features

- **User Management**: Activate/deactivate users
- **System Monitoring**: View activity logs and system stats
- **Security Overview**: Monitor encryption and access patterns

## 🔒 Security Features

### Encryption
- **AES-256-CBC**: Industry-standard encryption
- **Random Key Generation**: Unique keys for each file
- **Client-Side Encryption**: Files encrypted before upload

### Key Management
- **Steganographic Storage**: Keys hidden in profile pictures
- **Zero Transmission**: No keys sent during normal operations
- **Local Extraction**: Keys extracted client-side only

### Privacy
- **Searchable Encryption**: Search without revealing terms
- **Zero-Knowledge**: Server never sees unencrypted data
- **Activity Logging**: Comprehensive audit trail

## 🧪 Testing

Run the test suite:
```bash
python -m pytest tests/
```

Run specific test categories:
```bash
python -m pytest tests/test_app.py::EncCloudStorageTestCase
python -m pytest tests/test_app.py::SecurityTestCase
```

## 🚀 Deployment

### Production Deployment

1. **Set up production database**
   ```bash
   # PostgreSQL
   createdb enccloudstorage
   ```

2. **Configure environment**
   ```bash
   export FLASK_ENV=production
   export DATABASE_URL=postgresql://user:pass@localhost/enccloudstorage
   export SECRET_KEY=your-production-secret-key
   ```

3. **Deploy with Docker**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

### Azure Deployment

1. **Create Azure resources**
   - Storage Account
   - App Service
   - PostgreSQL Database

2. **Configure Azure App Service**
   - Set environment variables
   - Enable managed identity
   - Configure custom domain

## 📊 Monitoring

### Logs
- Application logs: `app.log`
- Activity logs: Database table `activity_log`
- Security events: Logged with user context

### Metrics
- File upload/download counts
- User activity patterns
- Encryption/decryption operations
- Search operations

## 🔧 Development

### Project Structure
```
enccloudstorage/
├── app.py                 # Main Flask application
├── config.py             # Configuration management
├── run.py                # Application runner
├── requirements.txt      # Python dependencies
├── Dockerfile           # Container configuration
├── docker-compose.yml   # Multi-service setup
├── templates/          # HTML templates
├── static/             # CSS, JS, images
├── tests/              # Test suite
└── uploads/            # Local file storage
```

### Adding Features

1. **Database Models**: Add to `app.py`
2. **Routes**: Implement in `app.py`
3. **Templates**: Create in `templates/`
4. **Static Files**: Add to `static/`
5. **Tests**: Add to `tests/`

### Code Style
- Follow PEP 8
- Use type hints where possible
- Document functions and classes
- Write tests for new features

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Submit pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Documentation**: Check README files
- **Issues**: GitHub Issues
- **Security**: Report security issues privately

## 🔮 Roadmap

- [ ] NLP-based keyword extraction
- [ ] Advanced search features
- [ ] Mobile application
- [ ] API endpoints
- [ ] Multi-tenant support
- [ ] Advanced analytics
- [ ] Backup and recovery
- [ ] Performance optimization

---

**EncCloudStorage** - Privacy-Preserving Cloud Storage with Searchable Encryption and Steganographic Key Management
