# app/models/point.py
"""ポイントシステム関連モデル"""

from datetime import datetime
from ..extensions import db


class PointPackage(db.Model):
    """ポイント購入パッケージ"""
    __tablename__ = 'point_packages'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Integer, nullable=False)  # 円
    points = db.Column(db.Integer, nullable=False)  # 基本ポイント
    bonus_points = db.Column(db.Integer, default=0)  # ボーナスポイント
    
    description = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)  # おすすめ表示
    sort_order = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def total_points(self):
        """合計付与ポイント"""
        return self.points + self.bonus_points
    
    @property
    def bonus_rate(self):
        """ボーナス率（%）"""
        if self.points == 0:
            return 0
        return round((self.bonus_points / self.points) * 100)
    
    @property
    def price_display(self):
        """価格表示用"""
        return f"¥{self.price:,}"
    
    @classmethod
    def get_active_packages(cls):
        """有効なパッケージ一覧を取得"""
        return cls.query.filter_by(is_active=True).order_by(cls.sort_order, cls.price).all()
    
    def __repr__(self):
        return f'<PointPackage {self.name} ¥{self.price}>'


class PointTransaction(db.Model):
    """ポイント取引履歴"""
    __tablename__ = 'point_transactions'
    
    # 取引タイプ
    TYPE_PURCHASE = 'purchase'      # 購入
    TYPE_GIFT = 'gift'              # ギフト使用
    TYPE_REFUND = 'refund'          # 返金
    TYPE_BONUS = 'bonus'            # ボーナス付与
    TYPE_ADJUSTMENT = 'adjustment'  # 運営調整
    TYPE_EXPIRED = 'expired'        # 期限切れ
    
    TYPE_LABELS = {
        'purchase': 'ポイント購入',
        'gift': 'ギフト送信',
        'refund': '返金',
        'bonus': 'ボーナス',
        'adjustment': '調整',
        'expired': '期限切れ',
    }
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False, index=True)
    transaction_type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Integer, nullable=False)  # +購入/-使用
    balance_after = db.Column(db.Integer, nullable=False)  # 取引後残高
    
    # 購入時の情報
    package_id = db.Column(db.Integer, db.ForeignKey('point_packages.id'))
    payment_amount = db.Column(db.Integer)  # 支払い金額（円）
    stripe_payment_intent_id = db.Column(db.String(100))
    stripe_charge_id = db.Column(db.String(100))
    
    # ギフト使用時
    gift_transaction_id = db.Column(db.Integer, db.ForeignKey('gift_transactions.id', ondelete='SET NULL'))
    
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーション
    package = db.relationship('PointPackage')
    
    @property
    def type_label(self):
        """取引タイプの日本語ラベル"""
        return self.TYPE_LABELS.get(self.transaction_type, self.transaction_type)
    
    @property
    def is_credit(self):
        """入金（プラス）かどうか"""
        return self.amount > 0
    
    @property
    def amount_display(self):
        """金額表示用（+/-付き）"""
        if self.amount > 0:
            return f"+{self.amount:,}pt"
        return f"{self.amount:,}pt"
    
    def __repr__(self):
        return f'<PointTransaction {self.id} {self.transaction_type} {self.amount}>'
