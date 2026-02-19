# app/models/shop_point.py
"""店舗独自ポイントカード関連モデル"""

from datetime import datetime, date, timedelta
from sqlalchemy import func
from ..extensions import db


class ShopPointCard(db.Model):
    """店舗ポイントカード設定"""
    __tablename__ = 'shop_point_cards'
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    
    # ポイントカード設定
    is_active = db.Column(db.Boolean, default=True)  # ポイントカード機能有効
    card_name = db.Column(db.String(50), default='ポイントカード')  # カード名称
    
    # ランク制度
    rank_system_enabled = db.Column(db.Boolean, default=False)  # ランク制度ON/OFF
    
    # 来店ポイント設定
    visit_points = db.Column(db.Integer, default=100)  # 1回の来店で付与するポイント
    min_visit_interval_hours = db.Column(db.Integer, default=4)  # 最短来店間隔（時間）連続付与防止
    
    # 特典設定
    reward_threshold = db.Column(db.Integer, default=1000)  # 特典交換に必要なポイント
    reward_description = db.Column(db.String(200))  # 特典の説明（例: 「ドリンク1杯無料」）
    
    # デザイン設定（将来拡張用）
    card_color = db.Column(db.String(20), default='#6366f1')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーション
    shop = db.relationship('Shop', backref=db.backref('point_card', uselist=False))
    
    @classmethod
    def get_or_create(cls, shop_id):
        """店舗のポイントカード設定を取得または作成"""
        card = cls.query.filter_by(shop_id=shop_id).first()
        if not card:
            card = cls(shop_id=shop_id)
            db.session.add(card)
        return card
    
    def __repr__(self):
        return f'<ShopPointCard shop={self.shop_id}>'


class CustomerShopPoint(db.Model):
    """顧客の店舗別ポイント残高"""
    __tablename__ = 'customer_shop_points'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id', ondelete='CASCADE'), nullable=False, index=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # ポイント残高
    point_balance = db.Column(db.Integer, default=0, nullable=False)
    
    # 累計
    total_earned = db.Column(db.Integer, default=0)  # 累計獲得ポイント
    total_used = db.Column(db.Integer, default=0)    # 累計使用ポイント
    visit_count = db.Column(db.Integer, default=0)   # 来店回数
    
    # 最終来店日時（連続付与防止用）
    last_visit_at = db.Column(db.DateTime)
    
    # ランク（非正規化キャッシュ）
    current_rank_id = db.Column(db.Integer, db.ForeignKey('shop_point_ranks.id', ondelete='SET NULL'))
    current_rank_name = db.Column(db.String(50))    # 表示用キャッシュ
    current_rank_icon = db.Column(db.String(10))    # アイコンキャッシュ
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーション
    customer = db.relationship('Customer', backref=db.backref('shop_points', lazy='dynamic'))
    shop = db.relationship('Shop', backref=db.backref('customer_points', lazy='dynamic'))
    
    __table_args__ = (
        db.UniqueConstraint('customer_id', 'shop_id', name='uq_customer_shop_point'),
    )
    
    @classmethod
    def get_or_create(cls, customer_id, shop_id):
        """顧客の店舗ポイントを取得または作成"""
        point = cls.query.filter_by(customer_id=customer_id, shop_id=shop_id).first()
        if not point:
            point = cls(customer_id=customer_id, shop_id=shop_id)
            db.session.add(point)
        return point
    
    def can_earn_visit_points(self, min_interval_hours=4):
        """来店ポイントを獲得可能か（最短間隔チェック）"""
        if not self.last_visit_at:
            return True
        
        elapsed = datetime.utcnow() - self.last_visit_at
        return elapsed >= timedelta(hours=min_interval_hours)
    
    def add_points(self, points, reason='visit'):
        """ポイントを追加"""
        self.point_balance += points
        self.total_earned += points
        if reason == 'visit':
            self.visit_count += 1
            self.last_visit_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def use_points(self, points):
        """ポイントを使用"""
        if self.point_balance < points:
            raise ValueError('ポイント残高が不足しています')
        self.point_balance -= points
        self.total_used += points
        self.updated_at = datetime.utcnow()
    
    @property
    def progress_to_reward(self):
        """特典までの進捗率（%）"""
        card = ShopPointCard.query.filter_by(shop_id=self.shop_id).first()
        if not card or card.reward_threshold <= 0:
            return 0
        return min(100, round((self.point_balance / card.reward_threshold) * 100, 1))
    
    def __repr__(self):
        return f'<CustomerShopPoint customer={self.customer_id} shop={self.shop_id} balance={self.point_balance}>'


class ShopPointTransaction(db.Model):
    """店舗ポイント取引履歴"""
    __tablename__ = 'shop_point_transactions'
    
    # 取引タイプ
    TYPE_VISIT = 'visit'          # 来店ポイント
    TYPE_REWARD = 'reward'        # 特典交換
    TYPE_BONUS = 'bonus'          # ボーナス付与
    TYPE_ADJUSTMENT = 'adjustment'  # 調整（運営/店舗による）
    TYPE_EXPIRED = 'expired'      # 期限切れ
    
    TYPE_LABELS = {
        'visit': '来店ポイント',
        'reward': '特典交換',
        'bonus': 'ボーナス',
        'adjustment': '調整',
        'expired': '期限切れ',
    }
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id', ondelete='CASCADE'), nullable=False, index=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)
    
    transaction_type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Integer, nullable=False)  # +獲得/-使用
    balance_after = db.Column(db.Integer, nullable=False)  # 取引後残高
    
    description = db.Column(db.String(200))  # 詳細説明
    
    # 来店確認方法（将来のQRコード等対応用）
    verification_method = db.Column(db.String(20))  # 'qr', 'manual', 'checkin'
    verified_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))  # 店舗スタッフID
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーション
    customer = db.relationship('Customer')
    shop = db.relationship('Shop')
    
    @property
    def type_label(self):
        """取引タイプの日本語ラベル"""
        return self.TYPE_LABELS.get(self.transaction_type, self.transaction_type)
    
    @property
    def is_credit(self):
        """入金（プラス）かどうか"""
        return self.amount > 0
    
    @classmethod
    def log_visit(cls, customer_id, shop_id, points, balance_after, verified_by=None, method='manual'):
        """来店ポイント付与を記録"""
        transaction = cls(
            customer_id=customer_id,
            shop_id=shop_id,
            transaction_type=cls.TYPE_VISIT,
            amount=points,
            balance_after=balance_after,
            description='来店ポイント',
            verification_method=method,
            verified_by=verified_by
        )
        db.session.add(transaction)
        return transaction
    
    @classmethod
    def log_reward(cls, customer_id, shop_id, points_used, balance_after, reward_description):
        """特典交換を記録"""
        transaction = cls(
            customer_id=customer_id,
            shop_id=shop_id,
            transaction_type=cls.TYPE_REWARD,
            amount=-points_used,
            balance_after=balance_after,
            description=f'特典交換: {reward_description}'
        )
        db.session.add(transaction)
        return transaction
    
    def __repr__(self):
        return f'<ShopPointTransaction {self.id} {self.transaction_type} {self.amount}>'


class ShopPointReward(db.Model):
    """特典交換履歴"""
    __tablename__ = 'shop_point_rewards'
    
    STATUS_PENDING = 'pending'      # 未使用
    STATUS_USED = 'used'            # 使用済み
    STATUS_EXPIRED = 'expired'      # 期限切れ
    STATUS_CANCELLED = 'cancelled'  # キャンセル
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id', ondelete='CASCADE'), nullable=False, index=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)
    
    points_used = db.Column(db.Integer, nullable=False)
    reward_description = db.Column(db.String(200), nullable=False)
    
    status = db.Column(db.String(20), default=STATUS_PENDING)
    
    # 有効期限
    expires_at = db.Column(db.DateTime)
    
    # 使用時の情報
    used_at = db.Column(db.DateTime)
    used_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))  # 確認した店舗スタッフ
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーション
    customer = db.relationship('Customer')
    shop = db.relationship('Shop')
    
    def mark_as_used(self, staff_id=None):
        """使用済みにする"""
        self.status = self.STATUS_USED
        self.used_at = datetime.utcnow()
        self.used_by = staff_id
    
    @property
    def is_valid(self):
        """有効な特典か"""
        if self.status != self.STATUS_PENDING:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True
    
    def __repr__(self):
        return f'<ShopPointReward {self.id} {self.status}>'
