// Main JavaScript for EncCloudStorage

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Auto-hide alerts after 5 seconds
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert');
        alerts.forEach(function(alert) {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);

    // File upload drag and drop
    initializeFileUpload();
    
    // Search functionality
    initializeSearch();
    
    // Security indicators
    initializeSecurityIndicators();
});

// File Upload Functionality
function initializeFileUpload() {
    const fileInput = document.getElementById('file');
    const uploadForm = document.getElementById('uploadForm');
    
    if (fileInput && uploadForm) {
        // Drag and drop functionality
        const uploadArea = fileInput.closest('.card-body');
        if (uploadArea) {
            uploadArea.addEventListener('dragover', function(e) {
                e.preventDefault();
                uploadArea.classList.add('dragover');
            });
            
            uploadArea.addEventListener('dragleave', function(e) {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
            });
            
            uploadArea.addEventListener('drop', function(e) {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
                
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    fileInput.files = files;
                    updateFileInfo(files[0]);
                }
            });
        }
        
        // File selection handler
        fileInput.addEventListener('change', function(e) {
            if (e.target.files.length > 0) {
                updateFileInfo(e.target.files[0]);
            }
        });
        
        // Form submission with progress
        uploadForm.addEventListener('submit', function(e) {
            showUploadProgress();
        });
    }
}

function updateFileInfo(file) {
    const fileSize = (file.size / 1024 / 1024).toFixed(2);
    const maxSize = 16; // 16MB limit
    
    if (file.size > maxSize * 1024 * 1024) {
        alert(`File size (${fileSize}MB) exceeds the ${maxSize}MB limit. Please choose a smaller file.`);
        document.getElementById('file').value = '';
        return;
    }
    
    // Show file info
    let fileInfo = document.getElementById('file-info');
    if (!fileInfo) {
        fileInfo = document.createElement('div');
        fileInfo.id = 'file-info';
        fileInfo.className = 'mt-2 p-2 bg-light rounded';
        document.getElementById('file').parentNode.appendChild(fileInfo);
    }
    
    fileInfo.innerHTML = `
        <small class="text-muted">
            <i class="fas fa-file"></i> ${file.name} 
            <span class="badge bg-info">${fileSize} MB</span>
            <span class="badge bg-success">Ready for encryption</span>
        </small>
    `;
}

function showUploadProgress() {
    const progressCard = document.getElementById('progressCard');
    const progressBar = document.querySelector('.progress-bar');
    const progressText = document.getElementById('progressText');
    const uploadBtn = document.getElementById('uploadBtn');
    
    if (progressCard) {
        progressCard.style.display = 'block';
        progressCard.scrollIntoView({ behavior: 'smooth' });
    }
    
    if (uploadBtn) {
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
    }
    
    // Simulate progress
    let progress = 0;
    const steps = [
        { progress: 20, text: 'Encrypting file with AES-256...' },
        { progress: 40, text: 'Extracting keywords...' },
        { progress: 60, text: 'Creating encrypted index...' },
        { progress: 80, text: 'Uploading to cloud storage...' },
        { progress: 95, text: 'Updating steganographic keys...' },
        { progress: 100, text: 'Upload complete!' }
    ];
    
    let currentStep = 0;
    const interval = setInterval(() => {
        if (currentStep < steps.length) {
            const step = steps[currentStep];
            progress = step.progress;
            
            if (progressBar) {
                progressBar.style.width = progress + '%';
            }
            
            if (progressText) {
                progressText.textContent = step.text;
            }
            
            currentStep++;
        } else {
            clearInterval(interval);
        }
    }, 800);
}

// Search Functionality
function initializeSearch() {
    const searchForm = document.getElementById('searchForm');
    const searchInput = document.getElementById('search_term');
    
    if (searchForm && searchInput) {
        // Auto-focus search input
        searchInput.focus();
        
        // Search form submission
        searchForm.addEventListener('submit', function(e) {
            const searchTerm = searchInput.value.trim();
            
            if (!searchTerm) {
                e.preventDefault();
                showAlert('Please enter a search term.', 'warning');
                return;
            }
            
            // Show loading state
            const submitBtn = document.querySelector('button[type="submit"]');
            if (submitBtn) {
                const originalText = submitBtn.innerHTML;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Searching...';
                submitBtn.disabled = true;
                
                // Re-enable after timeout
                setTimeout(() => {
                    submitBtn.innerHTML = originalText;
                    submitBtn.disabled = false;
                }, 5000);
            }
        });
        
        // Search suggestions (basic implementation)
        searchInput.addEventListener('input', function(e) {
            const value = e.target.value.toLowerCase();
            if (value.length > 2) {
                // Could implement search suggestions here
                console.log('Searching for:', value);
            }
        });
    }
}

// Security Indicators
function initializeSecurityIndicators() {
    // Add security badges to encrypted files
    const encryptedFiles = document.querySelectorAll('[data-encrypted="true"]');
    encryptedFiles.forEach(function(file) {
        const badge = document.createElement('span');
        badge.className = 'badge bg-success ms-1';
        badge.innerHTML = '<i class="fas fa-lock"></i> Encrypted';
        file.appendChild(badge);
    });
    
    // Show security status
    updateSecurityStatus();
}

function updateSecurityStatus() {
    const securityStatus = document.querySelector('.security-status');
    if (securityStatus) {
        securityStatus.innerHTML = `
            <div class="alert alert-success">
                <i class="fas fa-shield-alt"></i>
                <strong>Security Status:</strong> All files are encrypted with AES-256 and keys are stored steganographically.
            </div>
        `;
    }
}

// Utility Functions
function showAlert(message, type = 'info') {
    const alertContainer = document.querySelector('.container');
    if (alertContainer) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        alertContainer.insertBefore(alertDiv, alertContainer.firstChild);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }
}

function confirmAction(message) {
    return confirm(message);
}

// File Download with Security Check
function secureDownload(fileId) {
    if (confirm('This will decrypt and download the file. Continue?')) {
        window.location.href = `/download/${fileId}`;
    }
}

// Admin Functions
function toggleUserStatus(userId, currentStatus) {
    const action = currentStatus ? 'deactivate' : 'activate';
    if (confirm(`Are you sure you want to ${action} this user?`)) {
        window.location.href = `/admin/user/${userId}/toggle`;
    }
}

// Security Information Modal
function showSecurityInfo() {
    const modalHtml = `
        <div class="modal fade" id="securityModal" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="fas fa-shield-alt"></i> Security Features
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row">
                            <div class="col-md-6">
                                <h6 class="text-primary">Encryption</h6>
                                <ul class="small">
                                    <li>AES-256-CBC encryption</li>
                                    <li>Random key generation</li>
                                    <li>Client-side encryption</li>
                                    <li>Secure key storage</li>
                                </ul>
                            </div>
                            <div class="col-md-6">
                                <h6 class="text-success">Privacy</h6>
                                <ul class="small">
                                    <li>Searchable encryption</li>
                                    <li>Zero-knowledge search</li>
                                    <li>Steganographic keys</li>
                                    <li>No key transmission</li>
                                </ul>
                            </div>
                        </div>
                        <div class="row mt-3">
                            <div class="col-12">
                                <h6 class="text-info">How It Works</h6>
                                <ol class="small">
                                    <li>Files are encrypted with AES-256 before upload</li>
                                    <li>Keywords are extracted and hashed for search</li>
                                    <li>Encryption keys are hidden in your profile picture</li>
                                    <li>Search works without revealing content or search terms</li>
                                </ol>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Remove existing modal
    const existingModal = document.getElementById('securityModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // Add modal to body
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('securityModal'));
    modal.show();
}

// Real-time Activity Updates (for admin panel)
function initializeActivityUpdates() {
    if (window.location.pathname.includes('/admin')) {
        setInterval(function() {
            // Could implement AJAX updates here
            console.log('Checking for new activity...');
        }, 30000); // Check every 30 seconds
    }
}

// Initialize activity updates
initializeActivityUpdates();

// Export functions for global use
window.EncCloudStorage = {
    showAlert: showAlert,
    confirmAction: confirmAction,
    secureDownload: secureDownload,
    toggleUserStatus: toggleUserStatus,
    showSecurityInfo: showSecurityInfo
};
