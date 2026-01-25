"""
Night-Walk MVP - User Models
"""
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from ..extensions import db, login_manager


class User(UserMixin, db.Model):
    """User model for authentication and authorization."""
    __tablename__ = 'users'
    
    # Roles
    ROLE_ADMIN = 'admin'    # 運営
    ROLE_OWNER = 'owner'    # 店舗オーナー
    ROLE_STAFF = 'staff'    # 店舗スタッフ
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_STAFF, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = db.Column(db.DateTime)
    
    # Relationships
    shop_memberships = db.relationship('ShopMember', back_populates='user', lazy='dynamic')
    
    def set_password(self, password):
        """Hash and set the password."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if the provided password matches."""
        return check_password_hash(self.password_hash, password)
    
    @property
    def is_admin(self):
        """Check if user is admin."""
        return self.role == self.ROLE_ADMIN
    
    def get_shops(self):
        """Get all shops the user has access to."""
        if self.is_admin:
            from .shop import Shop
            return Shop.query.filter_by(is_active=True).all()
        return [m.shop for m in self.shop_memberships if m.shop.is_active]
    
    def get_primary_shop(self):
        """Get the first shop for non-admin users."""
        shops = self.get_shops()
        return shops[0] if shops else None
    
    def can_access_shop(self, shop_id):
        """Check if user can access a specific shop."""
        if self.is_admin:
            return True
        return self.shop_memberships.filter_by(shop_id=shop_id).first() is not None
    
    def has_permission(self, permission, shop_id=None):
        """Check if user has a specific permission."""
        from ..utils.decorators import PERMISSIONS
        
        if self.is_admin:
            return True
        
        allowed_roles = PERMISSIONS.get(permission, [])
        
        if shop_id:
            membership = self.shop_memberships.filter_by(shop_id=shop_id).first()
            if membership:
                return membership.role in allowed_roles
        
        return self.role in allowed_roles
    
    def get_id(self):
        """Flask-Login用のID（Customerと区別するため）"""
        return str(self.id)
    
    @property
    def is_customer(self):
        """カスタマーかどうか（Userは常にFalse）"""
        return False
    
    def __repr__(self):
        return f'<User {self.email}>'


class ShopMember(db.Model):
    """Shop membership - links users to shops with roles."""
    __tablename__ = 'shop_members'
    
    ROLE_OWNER = 'owner'
    ROLE_STAFF = 'staff'
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False, default=ROLE_STAFF)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    shop = db.relationship('Shop', back_populates='members')
    user = db.relationship('User', back_populates='shop_memberships')
    
    __table_args__ = (
        db.UniqueConstraint('shop_id', 'user_id', name='uq_shop_user'),
    )
    
    @property
    def is_owner(self):
        """Check if this membership is owner level."""
        return self.role == self.ROLE_OWNER
    
    def __repr__(self):
        return f'<ShopMember shop={self.shop_id} user={self.user_id}>'
