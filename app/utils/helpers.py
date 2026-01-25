"""
Night-Walk MVP - Helper Functions
"""
from flask import request, flash


def get_client_ip():
    """Get client IP address, handling proxies."""
    if not request:
        return None
    
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    if request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    
    return request.remote_addr


def flash_errors(form):
    """Flash all form errors."""
    for field, errors in form.errors.items():
        for error in errors:
            field_label = getattr(form, field).label.text if hasattr(form, field) else field
            flash(f'{field_label}: {error}', 'danger')


def allowed_file(filename, allowed_extensions):
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions


# Allowed MIME types for image uploads
ALLOWED_IMAGE_MIMES = {
    'image/jpeg',
    'image/jpg', 
    'image/png',
    'image/gif',
    'image/webp',
}


def validate_image_file(file_storage):
    """
    Validate uploaded image file by checking both extension and MIME type.
    
    Args:
        file_storage: werkzeug FileStorage object
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not file_storage or not file_storage.filename:
        return False, 'ファイルが選択されていません'
    
    filename = file_storage.filename
    
    # Check extension
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    if not allowed_file(filename, allowed_extensions):
        return False, '許可されていないファイル形式です（PNG, JPG, GIF, WebPのみ）'
    
    # Check file size (read first 10MB max)
    file_storage.seek(0, 2)  # Seek to end
    file_size = file_storage.tell()
    file_storage.seek(0)  # Reset to beginning
    
    if file_size > 16 * 1024 * 1024:  # 16MB
        return False, 'ファイルサイズが大きすぎます（16MB以下）'
    
    if file_size == 0:
        return False, 'ファイルが空です'
    
    # Check MIME type using python-magic
    try:
        import magic
        
        # Read file header for MIME detection
        file_header = file_storage.read(2048)
        file_storage.seek(0)  # Reset to beginning
        
        mime = magic.Magic(mime=True)
        detected_mime = mime.from_buffer(file_header)
        
        if detected_mime not in ALLOWED_IMAGE_MIMES:
            return False, f'ファイル形式が不正です（検出: {detected_mime}）'
            
    except ImportError:
        # python-magic not installed, fall back to basic check
        pass
    except Exception as e:
        # Log but don't block if magic fails
        from flask import current_app
        current_app.logger.warning(f"MIME detection failed: {e}")
    
    # Additional check: verify image can be opened
    try:
        from PIL import Image
        file_storage.seek(0)
        img = Image.open(file_storage)
        img.verify()  # Verify it's a valid image
        file_storage.seek(0)  # Reset after verify
    except Exception as e:
        return False, '画像ファイルとして読み込めません'
    
    return True, None


def format_phone(phone):
    """Format phone number for display."""
    if not phone:
        return ''
    # Remove non-digits
    digits = ''.join(filter(str.isdigit, phone))
    # Format as Japanese phone number
    if len(digits) == 11:
        return f'{digits[:3]}-{digits[3:7]}-{digits[7:]}'
    elif len(digits) == 10:
        return f'{digits[:3]}-{digits[3:6]}-{digits[6:]}'
    return phone


def truncate_text(text, length=100):
    """Truncate text to specified length."""
    if not text:
        return ''
    if len(text) <= length:
        return text
    return text[:length] + '...'
