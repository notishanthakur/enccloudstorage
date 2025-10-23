"""
Test suite for EncCloudStorage application.
"""

import unittest
import tempfile
import os
from app import app, db, User, File, ActivityLog
from werkzeug.security import generate_password_hash

class EncCloudStorageTestCase(unittest.TestCase):
    """Test cases for the EncCloudStorage application."""
    
    def setUp(self):
        """Set up test environment."""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['WTF_CSRF_ENABLED'] = False
        
        self.client = self.app.test_client()
        
        with self.app.app_context():
            db.create_all()
            
            # Create test user
            self.test_user = User(
                username='testuser',
                email='test@example.com',
                password_hash=generate_password_hash('testpass'),
                user_level='user'
            )
            db.session.add(self.test_user)
            db.session.commit()
    
    def tearDown(self):
        """Clean up after tests."""
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
    
    def test_index_page(self):
        """Test the index page loads correctly."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'EncCloudStorage', response.data)
    
    def test_login_page(self):
        """Test the login page loads correctly."""
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Login', response.data)
    
    def test_register_page(self):
        """Test the register page loads correctly."""
        response = self.client.get('/register')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Register', response.data)
    
    def test_user_registration(self):
        """Test user registration functionality."""
        response = self.client.post('/register', data={
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'newpass123'
        })
        
        # Should redirect after successful registration
        self.assertEqual(response.status_code, 302)
        
        # Check user was created
        with self.app.app_context():
            user = User.query.filter_by(username='newuser').first()
            self.assertIsNotNone(user)
            self.assertEqual(user.email, 'newuser@example.com')
    
    def test_user_login(self):
        """Test user login functionality."""
        response = self.client.post('/login', data={
            'username': 'testuser',
            'password': 'testpass'
        })
        
        # Should redirect after successful login
        self.assertEqual(response.status_code, 302)
    
    def test_invalid_login(self):
        """Test invalid login credentials."""
        response = self.client.post('/login', data={
            'username': 'testuser',
            'password': 'wrongpass'
        })
        
        # Should stay on login page with error
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid username or password', response.data)
    
    def test_dashboard_requires_login(self):
        """Test that dashboard requires authentication."""
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_upload_requires_login(self):
        """Test that upload requires authentication."""
        response = self.client.get('/upload')
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_search_requires_login(self):
        """Test that search requires authentication."""
        response = self.client.get('/search')
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_admin_panel_access(self):
        """Test admin panel access control."""
        # Login as regular user
        self.client.post('/login', data={
            'username': 'testuser',
            'password': 'testpass'
        })
        
        # Try to access admin panel
        response = self.client.get('/admin')
        self.assertEqual(response.status_code, 302)  # Should redirect (access denied)
    
    def test_file_upload_workflow(self):
        """Test the complete file upload workflow."""
        # Login first
        self.client.post('/login', data={
            'username': 'testuser',
            'password': 'testpass'
        })
        
        # Create a test file
        test_content = b"Test file content for encryption"
        
        # Upload file
        response = self.client.post('/upload', data={
            'file': (io.BytesIO(test_content), 'test.txt'),
            'access_level': 'private'
        })
        
        # Should redirect to dashboard
        self.assertEqual(response.status_code, 302)
    
    def test_activity_logging(self):
        """Test that user activities are logged."""
        # Login
        self.client.post('/login', data={
            'username': 'testuser',
            'password': 'testpass'
        })
        
        # Check that login was logged
        with self.app.app_context():
            log = ActivityLog.query.filter_by(
                user_id=self.test_user.id,
                action='login'
            ).first()
            self.assertIsNotNone(log)
            self.assertTrue(log.success)
    
    def test_encryption_functions(self):
        """Test encryption and decryption functions."""
        from app import encrypt_file, decrypt_file, pad
        
        # Test padding
        test_data = b"test data"
        padded = pad(test_data)
        self.assertEqual(len(padded) % 16, 0)
        
        # Test encryption/decryption
        key = b"test_key_16_bytes"  # 16 bytes for AES
        encrypted = encrypt_file(test_data, key)
        decrypted = decrypt_file(encrypted, key)
        
        self.assertEqual(decrypted, test_data)
    
    def test_keyword_extraction(self):
        """Test keyword extraction functionality."""
        from app import extract_keywords, hash_keyword
        
        text = "This is a test document with important keywords"
        keywords = extract_keywords(text)
        
        self.assertIn("test", keywords)
        self.assertIn("document", keywords)
        self.assertIn("important", keywords)
        self.assertIn("keywords", keywords)
        
        # Test keyword hashing
        hash1 = hash_keyword("test")
        hash2 = hash_keyword("test")
        hash3 = hash_keyword("different")
        
        self.assertEqual(hash1, hash2)
        self.assertNotEqual(hash1, hash3)

class SecurityTestCase(unittest.TestCase):
    """Security-specific test cases."""
    
    def setUp(self):
        """Set up security test environment."""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = self.app.test_client()
        
        with self.app.app_context():
            db.create_all()
    
    def test_password_hashing(self):
        """Test that passwords are properly hashed."""
        from werkzeug.security import generate_password_hash, check_password_hash
        
        password = "test_password_123"
        hashed = generate_password_hash(password)
        
        # Hash should be different from original password
        self.assertNotEqual(password, hashed)
        
        # Hash should verify correctly
        self.assertTrue(check_password_hash(hashed, password))
        self.assertFalse(check_password_hash(hashed, "wrong_password"))
    
    def test_sql_injection_protection(self):
        """Test protection against SQL injection."""
        # This is handled by SQLAlchemy ORM, but we can test the interface
        response = self.client.post('/login', data={
            'username': "'; DROP TABLE users; --",
            'password': 'anything'
        })
        
        # Should not crash the application
        self.assertEqual(response.status_code, 200)
    
    def test_file_upload_security(self):
        """Test file upload security measures."""
        # Test file size limit
        large_content = b"x" * (17 * 1024 * 1024)  # 17MB
        
        response = self.client.post('/upload', data={
            'file': (io.BytesIO(large_content), 'large_file.txt')
        })
        
        # Should handle large files gracefully
        self.assertIn(response.status_code, [200, 302, 413])

if __name__ == '__main__':
    unittest.main()
