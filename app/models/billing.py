"""
Night-Walk MVP - Billing Models (Stripe)
"""
from datetime import datetime
from ..extensions import db


class Subscription(db.Model):
    """Subscription model - Stripe subscription state."""
    __tablename__ = 'subscriptions'
    
    # Plans
    PLAN_BASIC = 'basic'
    PLAN_PREMIUM = 'premium'
    
    # Statuses
    STATUS_TRIAL = 'trial'
    STATUS_ACTIVE = 'active'
    STATUS_PAST_DUE = 'past_due'
    STATUS_CANCELED = 'canceled'
    STATUS_UNPAID = 'unpaid'
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)
    stripe_customer_id = db.Column(db.String(100))
    stripe_subscription_id = db.Column(db.String(100), index=True)
    plan = db.Column(db.String(50), nullable=False, default=PLAN_BASIC)
    status = db.Column(db.String(30), nullable=False, default=STATUS_TRIAL, index=True)
    current_period_start = db.Column(db.DateTime)
    current_period_end = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    shop = db.relationship('Shop', back_populates='subscription')
    
    @property
    def is_active(self):
        """Check if subscription is in active state."""
        return self.status in [self.STATUS_TRIAL, self.STATUS_ACTIVE]
    
    @property
    def is_past_due(self):
        """Check if subscription is past due."""
        return self.status == self.STATUS_PAST_DUE
    
    @property
    def status_label(self):
        """Get Japanese label for status."""
        labels = {
            self.STATUS_TRIAL: 'トライアル',
            self.STATUS_ACTIVE: '有効',
            self.STATUS_PAST_DUE: '支払い遅延',
            self.STATUS_CANCELED: 'キャンセル済み',
            self.STATUS_UNPAID: '未払い',
        }
        return labels.get(self.status, self.status)
    
    def __repr__(self):
        return f'<Subscription shop={self.shop_id} status={self.status}>'


class BillingEvent(db.Model):
    """Billing event log - Stripe webhook events."""
    __tablename__ = 'billing_events'
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)
    stripe_event_id = db.Column(db.String(100))
    amount = db.Column(db.Integer)  # 円
    currency = db.Column(db.String(10), default='jpy')
    payload = db.Column(db.Text)  # JSON
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    shop = db.relationship('Shop', back_populates='billing_events')
    
    def __repr__(self):
        return f'<BillingEvent {self.event_type} shop={self.shop_id}>'
