# app/models/earning.py
"""収益管理モデル"""

from datetime import datetime
from ..extensions import db


class Earning(db.Model):
    """収益履歴（キャスト・店舗・運営共通）"""
    __tablename__ = 'earnings'
    
    # 収益タイプ
    TYPE_CAST = 'cast'
    TYPE_SHOP = 'shop'
    TYPE_PLATFORM = 'platform'
    
    TYPE_LABELS = {
        'cast': 'キャスト',
        'shop': '店舗',
        'platform': '運営',
    }
    
    # ステータス
    STATUS_PENDING = 'pending'      # 未確定
    STATUS_CONFIRMED = 'confirmed'  # 確定
    STATUS_PAID = 'paid'            # 支払済み
    
    STATUS_LABELS = {
        'pending': '未確定',
        'confirmed': '確定',
        'paid': '支払済み',
    }
    
    id = db.Column(db.Integer, primary_key=True)
    earning_type = db.Column(db.String(20), nullable=False, index=True)
    
    # 対象（タイプによりいずれか）
    cast_id = db.Column(db.Integer, db.ForeignKey('casts.id', ondelete='SET NULL'), index=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='SET NULL'), index=True)
    
    # 元となったギフト取引
    gift_transaction_id = db.Column(db.Integer, db.ForeignKey('gift_transactions.id', ondelete='SET NULL'))
    
    amount = db.Column(db.Integer, nullable=False)  # 円
    
    status = db.Column(db.String(20), default=STATUS_PENDING)
    confirmed_at = db.Column(db.DateTime)
    paid_at = db.Column(db.DateTime)
    
    # 支払い情報
    payment_note = db.Column(db.String(255))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーション
    cast = db.relationship('Cast', backref='earnings')
    shop = db.relationship('Shop', backref='gift_earnings')
    gift_transaction = db.relationship('GiftTransaction', backref='earnings')
    
    @property
    def type_label(self):
        """タイプの日本語ラベル"""
        return self.TYPE_LABELS.get(self.earning_type, self.earning_type)
    
    @property
    def status_label(self):
        """ステータスの日本語ラベル"""
        return self.STATUS_LABELS.get(self.status, self.status)
    
    def confirm(self):
        """確定にする"""
        self.status = self.STATUS_CONFIRMED
        self.confirmed_at = datetime.utcnow()
    
    def mark_paid(self, note=None):
        """支払済みにする"""
        self.status = self.STATUS_PAID
        self.paid_at = datetime.utcnow()
        if note:
            self.payment_note = note
    
    @classmethod
    def create_from_gift(cls, gift_transaction):
        """ギフト取引から収益レコードを作成"""
        earnings = []
        
        # キャスト収益
        cast_earning = cls(
            earning_type=cls.TYPE_CAST,
            cast_id=gift_transaction.cast_id,
            shop_id=gift_transaction.shop_id,
            gift_transaction_id=gift_transaction.id,
            amount=gift_transaction.cast_amount,
            status=cls.STATUS_PENDING
        )
        earnings.append(cast_earning)
        
        # 店舗収益
        shop_earning = cls(
            earning_type=cls.TYPE_SHOP,
            shop_id=gift_transaction.shop_id,
            gift_transaction_id=gift_transaction.id,
            amount=gift_transaction.shop_amount,
            status=cls.STATUS_PENDING
        )
        earnings.append(shop_earning)
        
        # 運営収益
        platform_earning = cls(
            earning_type=cls.TYPE_PLATFORM,
            gift_transaction_id=gift_transaction.id,
            amount=gift_transaction.platform_amount,
            status=cls.STATUS_CONFIRMED  # 運営は即確定
        )
        platform_earning.confirmed_at = datetime.utcnow()
        earnings.append(platform_earning)
        
        return earnings
    
    def __repr__(self):
        return f'<Earning {self.earning_type} ¥{self.amount}>'
