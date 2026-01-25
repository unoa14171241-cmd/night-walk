"""
Night-Walk MVP - Job Model
"""
from datetime import datetime, date
from ..extensions import db


class Job(db.Model):
    """Job posting model."""
    __tablename__ = 'jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=False, index=True)
    hourly_wage = db.Column(db.String(50))          # 例: '3,000円〜'
    benefits = db.Column(db.Text)                    # 待遇
    trial_available = db.Column(db.Boolean, nullable=False, default=False)  # 体験可否
    expires_at = db.Column(db.Date)                  # 掲載期限
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    shop = db.relationship('Shop', back_populates='jobs')
    
    @property
    def is_expired(self):
        """Check if job posting has expired."""
        if not self.expires_at:
            return False
        return date.today() > self.expires_at
    
    @property
    def is_visible(self):
        """Check if job posting should be visible."""
        return self.is_active and not self.is_expired
    
    @classmethod
    def get_active_jobs(cls):
        """Get all active and non-expired job postings."""
        today = date.today()
        return cls.query.filter(
            cls.is_active == True,
            (cls.expires_at == None) | (cls.expires_at >= today)
        ).all()
    
    def __repr__(self):
        return f'<Job shop={self.shop_id} active={self.is_active}>'
