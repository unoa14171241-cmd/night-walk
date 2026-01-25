"""
Night-Walk MVP - Audit Log Model
"""
from datetime import datetime
from ..extensions import db


class AuditLog(db.Model):
    """Audit log model - tracks important actions."""
    __tablename__ = 'audit_logs'
    
    # Action types
    ACTION_VACANCY_UPDATE = 'vacancy.update'
    ACTION_SHOP_CREATE = 'shop.create'
    ACTION_SHOP_EDIT = 'shop.edit'
    ACTION_SHOP_TOGGLE = 'shop.toggle'
    ACTION_JOB_UPDATE = 'job.update'
    ACTION_BOOKING_CREATE = 'booking.create'
    ACTION_BILLING_EVENT = 'billing.event'
    ACTION_USER_LOGIN = 'user.login'
    ACTION_USER_LOGOUT = 'user.logout'
    ACTION_USER_LOGIN_FAILED = 'user.login_failed'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    target_type = db.Column(db.String(50))  # 'shop', 'user', 'job', etc.
    target_id = db.Column(db.Integer)
    old_value = db.Column(db.Text)  # JSON
    new_value = db.Column(db.Text)  # JSON
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id])
    
    @classmethod
    def log(cls, action, user_id=None, target_type=None, target_id=None,
            old_value=None, new_value=None, ip_address=None, user_agent=None):
        """Create an audit log entry."""
        import json
        
        entry = cls(
            action=action,
            user_id=user_id,
            target_type=target_type,
            target_id=target_id,
            old_value=json.dumps(old_value, ensure_ascii=False) if old_value else None,
            new_value=json.dumps(new_value, ensure_ascii=False) if new_value else None,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.session.add(entry)
        return entry
    
    def __repr__(self):
        return f'<AuditLog {self.action} user={self.user_id}>'
