# app/models/gift.py
"""ギフト・キャスト関連モデル"""

from datetime import datetime
from flask import url_for
from ..extensions import db


class Cast(db.Model):
    """キャスト"""
    __tablename__ = 'casts'
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=False, index=True)
    
    name = db.Column(db.String(50), nullable=False)
    display_name = db.Column(db.String(50))  # 源氏名・表示名
    profile = db.Column(db.Text)  # 自己紹介
    image_filename = db.Column(db.String(255))
    
    # SNS
    twitter_url = db.Column(db.String(255))
    instagram_url = db.Column(db.String(255))
    
    is_active = db.Column(db.Boolean, default=True)
    is_accepting_gifts = db.Column(db.Boolean, default=True)  # ギフト受付中
    is_featured = db.Column(db.Boolean, default=False)  # 注目キャスト
    
    # 累計
    total_gifts_received = db.Column(db.Integer, default=0)  # 受け取ったギフト数
    total_points_received = db.Column(db.Integer, default=0)  # 受け取った総ポイント
    total_earnings = db.Column(db.Integer, default=0)  # 総収益（円）
    
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーション
    shop = db.relationship('Shop', backref='casts')
    gift_transactions = db.relationship('GiftTransaction', backref='cast', lazy='dynamic')
    
    @property
    def name_display(self):
        """表示名（display_nameがあればそちら）"""
        return self.display_name or self.name
    
    @property
    def image_url(self):
        """画像URL"""
        if self.image_filename:
            return url_for('static', filename=f'uploads/casts/{self.image_filename}')
        return url_for('static', filename='images/default_cast.png')
    
    def add_gift(self, points, earnings):
        """ギフト受け取り時の集計更新"""
        self.total_gifts_received += 1
        self.total_points_received += points
        self.total_earnings += earnings
    
    @classmethod
    def get_active_by_shop(cls, shop_id):
        """店舗のアクティブなキャスト一覧"""
        return cls.query.filter_by(
            shop_id=shop_id,
            is_active=True
        ).order_by(cls.sort_order, cls.name).all()
    
    def __repr__(self):
        return f'<Cast {self.name_display}>'


class Gift(db.Model):
    """ギフト定義"""
    __tablename__ = 'gifts'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255))
    points = db.Column(db.Integer, nullable=False)  # 必要ポイント
    image_filename = db.Column(db.String(255))
    
    # 分配率（%）- 合計100%
    cast_rate = db.Column(db.Integer, default=50)      # キャスト: 50%
    shop_rate = db.Column(db.Integer, default=20)      # 店舗: 20%
    platform_rate = db.Column(db.Integer, default=30)  # 運営: 30%
    
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def cast_amount(self):
        """キャスト取り分（円）"""
        return int(self.points * self.cast_rate / 100)
    
    @property
    def shop_amount(self):
        """店舗取り分（円）"""
        return int(self.points * self.shop_rate / 100)
    
    @property
    def platform_amount(self):
        """運営取り分（円）"""
        return int(self.points * self.platform_rate / 100)
    
    @property
    def image_url(self):
        """画像URL"""
        if self.image_filename:
            return url_for('static', filename=f'uploads/gifts/{self.image_filename}')
        return url_for('static', filename='images/default_gift.png')
    
    @classmethod
    def get_active_gifts(cls):
        """有効なギフト一覧"""
        return cls.query.filter_by(is_active=True).order_by(cls.sort_order, cls.points).all()
    
    def __repr__(self):
        return f'<Gift {self.name} {self.points}pt>'


class GiftTransaction(db.Model):
    """ギフト送信履歴"""
    __tablename__ = 'gift_transactions'
    
    STATUS_COMPLETED = 'completed'  # 完了
    STATUS_REFUNDED = 'refunded'    # 返金済み
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False, index=True)
    cast_id = db.Column(db.Integer, db.ForeignKey('casts.id'), nullable=False, index=True)
    gift_id = db.Column(db.Integer, db.ForeignKey('gifts.id'), nullable=False)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=False, index=True)
    
    points_used = db.Column(db.Integer, nullable=False)
    message = db.Column(db.String(200))  # 応援メッセージ
    
    # 分配金額（円）
    cast_amount = db.Column(db.Integer, nullable=False)
    shop_amount = db.Column(db.Integer, nullable=False)
    platform_amount = db.Column(db.Integer, nullable=False)
    
    status = db.Column(db.String(20), default=STATUS_COMPLETED)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーション
    gift = db.relationship('Gift')
    shop = db.relationship('Shop')
    
    @property
    def total_amount(self):
        """合計金額"""
        return self.cast_amount + self.shop_amount + self.platform_amount
    
    def __repr__(self):
        return f'<GiftTransaction {self.id} {self.points_used}pt>'
