# app/models/customer.py
"""一般ユーザー（お客様）モデル"""

import uuid
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from ..extensions import db


class Customer(UserMixin, db.Model):
    """一般ユーザー（お客様）"""
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    nickname = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20))  # 旧フィールド（互換性維持）
    
    # SMS認証用電話番号
    phone_number = db.Column(db.String(20), unique=True, index=True)
    phone_verified = db.Column(db.Boolean, default=False)  # SMS認証済み
    
    # 来店チェックイン用トークン
    checkin_token = db.Column(db.String(36), unique=True, index=True)
    
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)  # メール認証済み
    
    # ポイント残高
    point_balance = db.Column(db.Integer, default=0)
    
    # 累計
    total_purchased_points = db.Column(db.Integer, default=0)
    total_spent_points = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = db.Column(db.DateTime)
    
    # リレーション
    point_transactions = db.relationship('PointTransaction', backref='customer', lazy='dynamic')
    gift_transactions = db.relationship('GiftTransaction', backref='customer', lazy='dynamic')
    
    def set_password(self, password):
        """パスワードをハッシュ化して保存"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """パスワードを検証"""
        return check_password_hash(self.password_hash, password)
    
    # 会員登録ボーナスポイント
    REGISTRATION_BONUS = 500
    
    def add_points(self, amount, description=None):
        """ポイントを追加"""
        self.point_balance += amount
        self.total_purchased_points += amount
    
    def use_points(self, amount):
        """ポイントを使用（残高不足の場合はFalse）"""
        if self.point_balance < amount:
            return False
        self.point_balance -= amount
        self.total_spent_points += amount
        return True
    
    def can_use_points(self, amount):
        """ポイントを使用できるか確認"""
        return self.point_balance >= amount
    
    def ensure_checkin_token(self):
        """チェックイントークンがなければ生成"""
        if not self.checkin_token:
            self.checkin_token = str(uuid.uuid4())
        return self.checkin_token
    
    # Flask-Login用（管理者Userと区別するため）
    def get_id(self):
        return f"customer_{self.id}"
    
    @property
    def is_customer(self):
        """カスタマーかどうか"""
        return True
    
    @property
    def is_admin(self):
        """管理者かどうか（カスタマーは常にFalse）"""
        return False
    
    def __repr__(self):
        return f'<Customer {self.email}>'
