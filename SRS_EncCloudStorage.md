# Software Requirements Specification (SRS)
## EncCloudStorage: Secure Searchable Cloud Storage System

**Document Version:** 1.0  
**Date:** October 24, 2025  
**Author:** Ishan Thakur  
**Project:** EncCloudStorage  

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Overall Description](#2-overall-description)
3. [System Features](#3-system-features)
4. [External Interface Requirements](#4-external-interface-requirements)
5. [Non-Functional Requirements](#5-non-functional-requirements)
6. [Other Requirements](#6-other-requirements)

---

## 1. Introduction

### 1.1 Purpose

This Software Requirements Specification (SRS) document describes the functional and non-functional requirements for EncCloudStorage, a secure cloud storage system that provides searchable encryption capabilities with steganographic key management. The document is intended for developers, testers, and stakeholders involved in the system's development and deployment.

### 1.2 Scope

EncCloudStorage is a web-based application that enables users to:
- Securely store encrypted files in the cloud
- Search encrypted files without revealing content to the cloud provider
- Manage encryption keys using steganographic techniques
- Extract keywords from various file formats using NLP

### 1.3 Definitions, Acronyms, and Abbreviations

| Term | Definition |
|------|------------|
| AES | Advanced Encryption Standard |
| LSB | Least Significant Bit |
| NLP | Natural Language Processing |
| SRS | Software Requirements Specification |
| API | Application Programming Interface |
| UI | User Interface |
| UX | User Experience |

### 1.4 References

- IEEE Std 830-1998: IEEE Recommended Practice for Software Requirements Specifications
- RFC 7519: JSON Web Token (JWT)
- NIST SP 800-57: Recommendation for Key Management
- OWASP Top 10: Web Application Security Risks

### 1.5 Overview

This document is organized into six main sections covering system requirements, features, interfaces, and constraints.

---

## 2. Overall Description

### 2.1 Product Perspective

EncCloudStorage is a standalone web application that interfaces with:
- **Azure Blob Storage**: For encrypted file storage
- **SQLite Database**: For user and metadata management
- **Web Browser**: For user interface
- **File System**: For temporary file processing

### 2.2 Product Functions

The system provides the following core functions:

1. **User Management**
   - User registration and authentication
   - Session management
   - Password security

2. **File Operations**
   - Secure file upload and encryption
   - File download and decryption
   - File deletion

3. **Search Capabilities**
   - Keyword-based search
   - Content extraction from various file formats
   - Fuzzy matching

4. **Security Features**
   - AES-256 encryption
   - Steganographic key hiding
   - Secure key management

### 2.3 User Characteristics

#### 2.3.1 Primary Users
- **End Users**: Individuals requiring secure cloud storage
- **Students**: Academic users with document storage needs
- **Professionals**: Business users requiring confidential file storage

#### 2.3.2 User Skills
- Basic computer literacy
- Web browser navigation
- File upload/download operations

### 2.4 Constraints

#### 2.4.1 Technical Constraints
- Python 3.8+ required
- Flask web framework
- Azure Blob Storage account
- Modern web browser support

#### 2.4.2 Regulatory Constraints
- Data privacy compliance
- Encryption standards adherence
- Secure key management

### 2.5 Assumptions and Dependencies

#### 2.5.1 Assumptions
- Users have reliable internet connectivity
- Azure Blob Storage service is available
- Users understand basic file operations

#### 2.5.2 Dependencies
- Azure Blob Storage SDK
- Python cryptography libraries
- Steganography libraries
- File processing libraries (PyPDF2, python-docx, etc.)

---

## 3. System Features

### 3.1 User Authentication and Management

#### 3.1.1 User Registration
**Description**: Allow new users to create accounts

**Inputs**:
- Username (string, 3-50 characters)
- Email (string, valid email format)
- Password (string, minimum 8 characters)

**Processing**:
- Validate input format
- Check username/email uniqueness
- Hash password using Werkzeug
- Create user record in database

**Outputs**:
- Success message or error notification
- Redirect to login page

**Preconditions**: None

**Postconditions**: User account created in database

#### 3.1.2 User Login
**Description**: Authenticate existing users

**Inputs**:
- Username or email
- Password

**Processing**:
- Validate credentials
- Create user session
- Set session variables

**Outputs**:
- Redirect to dashboard or error message

**Preconditions**: User account exists

**Postconditions**: User session established

#### 3.1.3 User Logout
**Description**: Terminate user session

**Inputs**: None

**Processing**:
- Clear session data
- Redirect to login page

**Outputs**: Redirect to login page

**Preconditions**: User is logged in

**Postconditions**: User session terminated

### 3.2 File Upload and Encryption

#### 3.2.1 File Upload
**Description**: Securely upload and encrypt files

**Inputs**:
- File (binary data)
- Filename (string)

**Processing**:
1. Generate AES-256 encryption key
2. Encrypt file content
3. Extract keywords using NLP
4. Create search index
5. Upload encrypted file to Azure Blob Storage
6. Store metadata in database
7. Update steganographic key management

**Outputs**:
- Success confirmation
- File metadata display

**Preconditions**: User is authenticated

**Postconditions**: File encrypted and stored

#### 3.2.2 Content Extraction
**Description**: Extract text content from various file formats

**Supported Formats**:
- PDF (using PyPDF2 and PyMuPDF)
- DOCX (using python-docx)
- XLSX (using openpyxl)
- PPTX (using python-pptx)
- TXT, MD, CSV (direct text reading)

**Processing**:
1. Identify file type
2. Apply appropriate extraction method
3. Extract text content
4. Generate keywords using NLP

**Outputs**: Extracted text content

**Preconditions**: Valid file format

**Postconditions**: Text content extracted

### 3.3 Search Functionality

#### 3.3.1 Keyword Search
**Description**: Search encrypted files using keywords

**Inputs**:
- Search query (string)

**Processing**:
1. Extract keywords from search query
2. Generate keyword hashes
3. Search steganographic index
4. Retrieve matching files
5. Decrypt and display results

**Outputs**:
- List of matching files
- File metadata
- Download links

**Preconditions**: User has uploaded files

**Postconditions**: Search results displayed

#### 3.3.2 Advanced Search
**Description**: Support for complex search queries

**Features**:
- Multiple keyword search
- File type filtering
- Date range filtering
- Fuzzy matching

**Processing**:
1. Parse search query
2. Apply filters
3. Execute search algorithm
4. Rank results by relevance

**Outputs**: Ranked search results

### 3.4 Steganographic Key Management

#### 3.4.1 Key Hiding
**Description**: Hide encryption keys and search indexes in profile images

**Processing**:
1. Generate or retrieve profile image
2. Build comprehensive search index
3. Create JSON payload with keys and index
4. Embed payload using LSB steganography
5. Save steganographic image

**Outputs**: Steganographic image with hidden data

**Preconditions**: User has uploaded files

**Postconditions**: Keys and index hidden in image

#### 3.4.2 Key Retrieval
**Description**: Extract keys and indexes from steganographic image

**Processing**:
1. Load steganographic image
2. Extract hidden payload
3. Parse JSON data
4. Retrieve keys and index

**Outputs**: Decryption keys and search index

**Preconditions**: Valid steganographic image exists

**Postconditions**: Keys and index available for use

### 3.5 File Download and Decryption

#### 3.5.1 File Download
**Description**: Download and decrypt files

**Inputs**:
- File ID or filename

**Processing**:
1. Retrieve encrypted file from Azure Blob Storage
2. Get decryption key from steganographic image
3. Decrypt file content
4. Stream file to user

**Outputs**: Decrypted file download

**Preconditions**: User has access to file

**Postconditions**: File downloaded and decrypted

---

## 4. External Interface Requirements

### 4.1 User Interfaces

#### 4.1.1 Web Interface
**Description**: HTML-based web interface

**Requirements**:
- Responsive design for desktop and mobile
- Modern, intuitive user interface
- Loading indicators for long operations
- Error message display
- File upload progress indicators

**Pages**:
- Login/Registration page
- Dashboard
- File upload page
- Search page
- File management page

#### 4.1.2 Navigation
**Description**: Intuitive navigation system

**Requirements**:
- Clear menu structure
- Breadcrumb navigation
- Back button functionality
- Quick access to common functions

### 4.2 Hardware Interfaces

#### 4.2.1 Server Requirements
- **CPU**: Minimum 2 cores, 2.4 GHz
- **RAM**: Minimum 4 GB
- **Storage**: 50 GB available space
- **Network**: High-speed internet connection

#### 4.2.2 Client Requirements
- **Browser**: Modern web browser (Chrome, Firefox, Safari, Edge)
- **JavaScript**: Enabled
- **Network**: Stable internet connection

### 4.3 Software Interfaces

#### 4.3.1 Azure Blob Storage
**Interface**: REST API
**Authentication**: Azure credentials
**Operations**: Upload, download, delete, list

#### 4.3.2 Database
**Interface**: SQLAlchemy ORM
**Database**: SQLite (development), PostgreSQL (production)
**Operations**: CRUD operations for users and files

### 4.4 Communications Interfaces

#### 4.4.1 HTTP/HTTPS
**Protocol**: HTTP/1.1, HTTPS for security
**Ports**: 80 (HTTP), 443 (HTTPS)
**Security**: TLS 1.2+ encryption

#### 4.4.2 API Endpoints
**Authentication**: Session-based
**Data Format**: JSON
**Error Handling**: HTTP status codes

---

## 5. Non-Functional Requirements

### 5.1 Performance Requirements

#### 5.1.1 Response Time
- **Page Load**: < 2 seconds
- **File Upload**: < 10 seconds (1 MB file)
- **Search Results**: < 3 seconds
- **File Download**: < 5 seconds (1 MB file)

#### 5.1.2 Throughput
- **Concurrent Users**: 100+ simultaneous users
- **File Upload Rate**: 10 files per minute per user
- **Search Queries**: 50+ queries per minute

#### 5.1.3 Scalability
- **Horizontal Scaling**: Support for multiple server instances
- **Database Scaling**: Support for database clustering
- **Storage Scaling**: Unlimited cloud storage capacity

### 5.2 Security Requirements

#### 5.2.1 Data Encryption
- **File Encryption**: AES-256-CBC
- **Key Management**: Secure key storage and distribution
- **Transmission**: TLS 1.2+ for all communications

#### 5.2.2 Authentication
- **Password Security**: Bcrypt hashing
- **Session Management**: Secure session handling
- **Access Control**: User-based access restrictions

#### 5.2.3 Privacy
- **Data Privacy**: Cloud provider cannot access user data
- **Metadata Protection**: Search indexes encrypted and hidden
- **Steganographic Security**: Keys hidden in images

### 5.3 Reliability Requirements

#### 5.3.1 Availability
- **Uptime**: 99.9% availability
- **Backup**: Daily automated backups
- **Recovery**: < 4 hours recovery time

#### 5.3.2 Fault Tolerance
- **Error Handling**: Graceful error handling
- **Data Integrity**: Checksums for file integrity
- **Transaction Safety**: ACID compliance

### 5.4 Usability Requirements

#### 5.4.1 User Experience
- **Learning Curve**: < 30 minutes for basic operations
- **Interface**: Intuitive, user-friendly design
- **Documentation**: Comprehensive help system

#### 5.4.2 Accessibility
- **Standards**: WCAG 2.1 AA compliance
- **Browser Support**: Cross-browser compatibility
- **Mobile Support**: Responsive design

### 5.5 Maintainability Requirements

#### 5.5.1 Code Quality
- **Documentation**: Comprehensive code documentation
- **Testing**: Unit and integration tests
- **Version Control**: Git-based version control

#### 5.5.2 Deployment
- **Automation**: Automated deployment pipeline
- **Monitoring**: Application performance monitoring
- **Logging**: Comprehensive logging system

---

## 6. Other Requirements

### 6.1 Legal Requirements

#### 6.1.1 Data Protection
- **GDPR Compliance**: European data protection standards
- **Data Retention**: Configurable data retention policies
- **User Consent**: Explicit consent for data processing

#### 6.1.2 Intellectual Property
- **Open Source**: Use of open-source libraries
- **Licensing**: Proper license compliance
- **Attribution**: Proper attribution of third-party components

### 6.2 Regulatory Requirements

#### 6.2.1 Encryption Standards
- **NIST Compliance**: NIST SP 800-57 key management
- **FIPS Compliance**: FIPS 140-2 validated algorithms
- **Export Control**: Compliance with export regulations

### 6.3 Environmental Requirements

#### 6.3.1 Operating Environment
- **Temperature**: 0-40°C operating temperature
- **Humidity**: 10-90% relative humidity
- **Power**: Standard electrical requirements

#### 6.3.2 Cloud Environment
- **Azure Compliance**: Azure security and compliance standards
- **Data Residency**: Configurable data location
- **Backup**: Automated backup and recovery

### 6.4 Business Requirements

#### 6.4.1 Cost Management
- **Storage Costs**: Optimized cloud storage usage
- **Bandwidth**: Efficient data transfer
- **Compute**: Resource optimization

#### 6.4.2 Scalability
- **User Growth**: Support for increasing user base
- **Data Growth**: Support for increasing data volume
- **Feature Growth**: Extensible architecture

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **AES** | Advanced Encryption Standard, symmetric encryption algorithm |
| **Blob** | Binary Large Object, Azure storage unit |
| **CBC** | Cipher Block Chaining, encryption mode |
| **LSB** | Least Significant Bit, steganography technique |
| **NLP** | Natural Language Processing, AI text analysis |
| **SHA** | Secure Hash Algorithm, cryptographic hash function |
| **Steganography** | Hiding information within other data |

## Appendix B: Acronyms

- **API**: Application Programming Interface
- **CRUD**: Create, Read, Update, Delete
- **GDPR**: General Data Protection Regulation
- **HTTP**: Hypertext Transfer Protocol
- **HTTPS**: HTTP Secure
- **JSON**: JavaScript Object Notation
- **NIST**: National Institute of Standards and Technology
- **OWASP**: Open Web Application Security Project
- **REST**: Representational State Transfer
- **SQL**: Structured Query Language
- **TLS**: Transport Layer Security
- **UI**: User Interface
- **URL**: Uniform Resource Locator
- **WCAG**: Web Content Accessibility Guidelines

---

**Document Control**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-10-24 | Ishan Thakur | Initial version |

---

*This Software Requirements Specification document provides comprehensive requirements for the EncCloudStorage system, ensuring secure, searchable cloud storage with steganographic key management capabilities.*
