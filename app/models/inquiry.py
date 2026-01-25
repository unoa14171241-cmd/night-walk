"""
Night-Walk MVP - Inquiry Model
"""
from datetime import datetime
from ..extensions import db


class Inquiry(db.Model):
    """Inquiry/Contact form model."""
    __tablename__ = 'inquiries'
    
    # Statuses
    STATUS_NEW = 'new'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_CLOSED = 'closed'
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'))  # NULLなら運営宛
    name = db.Column(db.String(100))
    email = db.Column(db.String(255))
    phone = db.Column(db.String(20))
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=STATUS_NEW, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    shop = db.relationship('Shop', back_populates='inquiries')
    
    @property
    def status_label(self):
        """Get Japanese label for status."""
        labels = {
            self.STATUS_NEW: '新規',
            self.STATUS_IN_PROGRESS: '対応中',
            self.STATUS_CLOSED: '完了',
        }
        return labels.get(self.status, self.status)
    
    def __repr__(self):
        return f'<Inquiry {self.id} status={self.status}>'
