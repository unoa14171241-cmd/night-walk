"""
Night-Walk MVP - Audit Logger
"""
from flask import request
from flask_login import current_user
from ..extensions import db
from ..models.audit import AuditLog


def audit_log(action, target_type=None, target_id=None, old_value=None, new_value=None, customer_id=None):
    """
    Log an audit event.
    
    Args:
        action: Action type (e.g., 'vacancy.update')
        target_type: Target entity type (e.g., 'shop')
        target_id: Target entity ID
        old_value: Previous value (dict)
        new_value: New value (dict)
        customer_id: Customer ID (for customer actions)
    """
    try:
        # Get user_id only if it's a User (not Customer)
        user_id = None
        if current_user.is_authenticated:
            if not hasattr(current_user, 'is_customer') or not current_user.is_customer:
                user_id = current_user.id
        ip_address = get_client_ip()
        user_agent = request.headers.get('User-Agent', '')[:500] if request else None
        
        entry = AuditLog.log(
            action=action,
            user_id=user_id,
            target_type=target_type,
            target_id=target_id,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        db.session.commit()
        return entry
        
    except Exception as e:
        # Don't fail the main operation if audit logging fails
        db.session.rollback()
        print(f"Audit log error: {e}")
        return None


def get_client_ip():
    """Get client IP address, handling proxies."""
    if not request:
        return None
    
    # Check for forwarded headers (reverse proxy)
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    if request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    
    return request.remote_addr
