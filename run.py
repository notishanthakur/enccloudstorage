#!/usr/bin/env python3
"""
EncCloudStorage - Privacy-Preserving Cloud Storage Application
Run script for development and production deployment.
"""

import os
import sys
from app import app, db
from config import config

def create_app(config_name=None):
    """Create and configure the Flask application."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app.config.from_object(config[config_name])
    
    # Initialize database
    with app.app_context():
        db.create_all()
        
        # Create admin user if none exists
        from app import User
        from werkzeug.security import generate_password_hash
        
        if not User.query.filter_by(user_level='admin').first():
            admin = User(
                username='admin',
                email=app.config['ADMIN_EMAIL'],
                password_hash=generate_password_hash(app.config['DEFAULT_ADMIN_PASSWORD']),
                user_level='admin'
            )
            db.session.add(admin)
            db.session.commit()
            print("[SUCCESS] Default admin user created (username: admin, password: {})".format(app.config['DEFAULT_ADMIN_PASSWORD']))
    
    return app

def main():
    """Main entry point for the application."""
    # Create application
    app_instance = create_app()
    
    # Get configuration
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    print("[STARTUP] Starting EncCloudStorage...")
    print("[INFO] Environment: {}".format(os.environ.get('FLASK_ENV', 'development')))
    print("[INFO] Server: http://{}:{}".format(host, port))
    print("[INFO] Debug: {}".format(debug))
    print("[INFO] Security: AES-256 + Steganography + Searchable Encryption")
    
    # Run application
    app_instance.run(host=host, port=port, debug=debug)

if __name__ == '__main__':
    main()
