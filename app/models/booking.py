"""
Night-Walk MVP - Booking/Call Models (Twilio)
"""
from datetime import datetime
from ..extensions import db


class Call(db.Model):
    """Twilio call log model."""
    __tablename__ = 'calls'
    
    # Call statuses
    STATUS_INITIATED = 'initiated'
    STATUS_RINGING = 'ringing'
    STATUS_ANSWERED = 'answered'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_NO_ANSWER = 'no-answer'
    STATUS_BUSY = 'busy'
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=False, index=True)
    call_sid = db.Column(db.String(100), unique=True, index=True)  # Twilio Call SID
    caller_number = db.Column(db.String(20))
    status = db.Column(db.String(30))
    duration = db.Column(db.Integer)  # 通話秒数
    digits_pressed = db.Column(db.String(10))  # プッシュ番号
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    ended_at = db.Column(db.DateTime)
    
    # Relationships
    shop = db.relationship('Shop', back_populates='calls')
    booking_log = db.relationship('BookingLog', back_populates='call', uselist=False)
    
    @property
    def is_successful(self):
        """Check if call was successful."""
        return self.status == self.STATUS_COMPLETED
    
    def __repr__(self):
        return f'<Call {self.call_sid} shop={self.shop_id}>'


class BookingLog(db.Model):
    """Booking log model - records reservation attempts."""
    __tablename__ = 'booking_logs'
    
    # Booking types
    TYPE_PHONE = 'phone'
    
    # Booking statuses
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_NO_ANSWER = 'no_answer'
    STATUS_FAILED = 'failed'
    
    id = db.Column(db.Integer, primary_key=True)
    call_id = db.Column(db.Integer, db.ForeignKey('calls.id'), index=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=False, index=True)
    booking_type = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Relationships
    call = db.relationship('Call', back_populates='booking_log')
    shop = db.relationship('Shop', back_populates='booking_logs')
    
    def __repr__(self):
        return f'<BookingLog shop={self.shop_id} status={self.status}>'
