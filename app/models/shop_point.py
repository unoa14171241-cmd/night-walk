# app/models/shop_point.py
"""店舗スタンプカード関連モデル"""

from datetime import datetime, date, timedelta
from sqlalchemy import func
from ..extensions import db


class ShopPointCard(db.Model):
    """店舗スタンプカード設定"""
    __tablename__ = 'shop_point_cards'
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    
    # 基本設定
    is_active = db.Column(db.Boolean, default=True)
    card_name = db.Column(db.String(50), default='スタンプカード')
    
    # ランク制度
    rank_system_enabled = db.Column(db.Boolean, default=False)
    
    # スタンプ設定
    max_stamps = db.Column(db.Integer, default=10)            # スタンプ数（デフォルト10）
    min_visit_interval_hours = db.Column(db.Integer, default=4)
    
    # 旧ポイント設定（後方互換）
    visit_points = db.Column(db.Integer, default=1)           # 1回=1スタンプ
    reward_threshold = db.Column(db.Integer, default=10)      # 10スタンプで特典
    
    # 特典設定
    reward_description = db.Column(db.String(200))
    
    # デザイン設定
    card_color = db.Column(db.String(20), default='#6366f1')
    card_image_url = db.Column(db.String(500))               # 店舗独自カード画像
    
    # テンプレート選択
    # 'bronze', 'silver', 'gold', 'platinum', 'bronze_num', 'silver_num', 'gold_num', 'platinum_num', 'custom'
    card_template = db.Column(db.String(30), default='bronze')
    show_stamp_numbers = db.Column(db.Boolean, default=True)  # スタンプに番号を表示
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーション
    shop = db.relationship('Shop', backref=db.backref('point_card', uselist=False))
    
    # テンプレート定義
    TEMPLATES = {
        'bronze':       {'label': 'ブロンズ',   'color': '#CD7F32', 'bg': 'linear-gradient(135deg, #CD7F32 0%, #A0522D 50%, #8B6914 100%)'},
        'silver':       {'label': 'シルバー',   'color': '#C0C0C0', 'bg': 'linear-gradient(135deg, #C0C0C0 0%, #A8A8A8 50%, #808080 100%)'},
        'gold':         {'label': 'ゴールド',   'color': '#FFD700', 'bg': 'linear-gradient(135deg, #FFD700 0%, #DAA520 50%, #B8860B 100%)'},
        'platinum':     {'label': 'プラチナ',   'color': '#E5E4E2', 'bg': 'linear-gradient(135deg, #E5E4E2 0%, #BDC3C7 50%, #95A5A6 100%)'},
        'custom':       {'label': 'カスタム',   'color': '#6366f1', 'bg': None},
    }
    
    @property
    def template_info(self):
        """テンプレート情報を取得"""
        return self.TEMPLATES.get(self.card_template or 'bronze', self.TEMPLATES['bronze'])
    
    @classmethod
    def get_or_create(cls, shop_id):
        """店舗のスタンプカード設定を取得または作成"""
        card = cls.query.filter_by(shop_id=shop_id).first()
        if not card:
            card = cls(shop_id=shop_id)
            db.session.add(card)
        return card
    
    def __repr__(self):
        return f'<ShopPointCard shop={self.shop_id}>'


class CustomerShopPoint(db.Model):
    """顧客の店舗別スタンプ残高"""
    __tablename__ = 'customer_shop_points'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id', ondelete='CASCADE'), nullable=False, index=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # スタンプ残高（旧: point_balance）
    point_balance = db.Column(db.Integer, default=0, nullable=False)
    
    # 累計
    total_earned = db.Column(db.Integer, default=0)
    total_used = db.Column(db.Integer, default=0)
    visit_count = db.Column(db.Integer, default=0)
    
    # 最終来店日時
    last_visit_at = db.Column(db.DateTime)
    
    # ランク
    current_rank_id = db.Column(db.Integer, db.ForeignKey('shop_point_ranks.id', ondelete='SET NULL'))
    current_rank_name = db.Column(db.String(50))
    current_rank_icon = db.Column(db.String(10))
    
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
        """顧客のスタンプカードを取得または作成"""
        point = cls.query.filter_by(customer_id=customer_id, shop_id=shop_id).first()
        if not point:
            point = cls(customer_id=customer_id, shop_id=shop_id,
                        point_balance=0, total_earned=0, total_used=0, visit_count=0)
            db.session.add(point)
        else:
            if point.point_balance is None:
                point.point_balance = 0
            if point.total_earned is None:
                point.total_earned = 0
            if point.total_used is None:
                point.total_used = 0
            if point.visit_count is None:
                point.visit_count = 0
        return point
    
    def can_earn_visit_points(self, min_interval_hours=4):
        """スタンプを獲得可能か（最短間隔チェック）"""
        if not self.last_visit_at:
            return True
        elapsed = datetime.utcnow() - self.last_visit_at
        return elapsed >= timedelta(hours=min_interval_hours)
    
    def add_points(self, points, reason='visit'):
        """スタンプを追加"""
        self.point_balance = (self.point_balance or 0) + points
        self.total_earned = (self.total_earned or 0) + points
        if reason == 'visit':
            self.visit_count = (self.visit_count or 0) + 1
            self.last_visit_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def use_points(self, points):
        """スタンプを使用（特典交換）"""
        balance = self.point_balance or 0
        if balance < points:
            raise ValueError('スタンプが不足しています')
        self.point_balance = balance - points
        self.total_used = (self.total_used or 0) + points
        self.updated_at = datetime.utcnow()
    
    @property
    def stamps_in_current_card(self):
        """現在のカードのスタンプ数（10個ごとにリセット表示）"""
        card = ShopPointCard.query.filter_by(shop_id=self.shop_id).first()
        max_stamps = card.max_stamps if card else 10
        return self.point_balance % max_stamps if max_stamps > 0 else self.point_balance
    
    @property
    def completed_cards(self):
        """完了したカード枚数"""
        card = ShopPointCard.query.filter_by(shop_id=self.shop_id).first()
        max_stamps = card.max_stamps if card else 10
        return self.point_balance // max_stamps if max_stamps > 0 else 0
    
    @property
    def progress_to_reward(self):
        """特典までの進捗率（%）"""
        card = ShopPointCard.query.filter_by(shop_id=self.shop_id).first()
        if not card or card.reward_threshold <= 0:
            return 0
        current = self.point_balance % card.reward_threshold if card.reward_threshold > 0 else self.point_balance
        return min(100, round((current / card.reward_threshold) * 100, 1))
    
    def __repr__(self):
        return f'<CustomerShopPoint customer={self.customer_id} shop={self.shop_id} stamps={self.point_balance}>'


class ShopPointTransaction(db.Model):
    """店舗スタンプ取引履歴"""
    __tablename__ = 'shop_point_transactions'
    
    TYPE_VISIT = 'visit'
    TYPE_REWARD = 'reward'
    TYPE_BONUS = 'bonus'
    TYPE_ADJUSTMENT = 'adjustment'
    TYPE_EXPIRED = 'expired'
    
    TYPE_LABELS = {
        'visit': 'スタンプ',
        'reward': '特典交換',
        'bonus': 'ボーナス',
        'adjustment': '調整',
        'expired': '期限切れ',
    }
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id', ondelete='CASCADE'), nullable=False, index=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)
    
    transaction_type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    balance_after = db.Column(db.Integer, nullable=False)
    
    description = db.Column(db.String(200))
    
    verification_method = db.Column(db.String(20))
    verified_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーション
    customer = db.relationship('Customer')
    shop = db.relationship('Shop')
    
    @property
    def type_label(self):
        return self.TYPE_LABELS.get(self.transaction_type, self.transaction_type)
    
    @property
    def is_credit(self):
        return self.amount > 0
    
    @classmethod
    def log_visit(cls, customer_id, shop_id, points, balance_after, verified_by=None, method='manual'):
        """スタンプ付与を記録"""
        transaction = cls(
            customer_id=customer_id,
            shop_id=shop_id,
            transaction_type=cls.TYPE_VISIT,
            amount=points,
            balance_after=balance_after,
            description='スタンプ付与',
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
    
    STATUS_PENDING = 'pending'
    STATUS_USED = 'used'
    STATUS_EXPIRED = 'expired'
    STATUS_CANCELLED = 'cancelled'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id', ondelete='CASCADE'), nullable=False, index=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)
    
    points_used = db.Column(db.Integer, nullable=False)
    reward_description = db.Column(db.String(200), nullable=False)
    
    status = db.Column(db.String(20), default=STATUS_PENDING)
    
    expires_at = db.Column(db.DateTime)
    
    used_at = db.Column(db.DateTime)
    used_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーション
    customer = db.relationship('Customer')
    shop = db.relationship('Shop')
    
    def mark_as_used(self, staff_id=None):
        self.status = self.STATUS_USED
        self.used_at = datetime.utcnow()
        self.used_by = staff_id
    
    @property
    def is_valid(self):
        if self.status != self.STATUS_PENDING:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True
    
    def __repr__(self):
        return f'<ShopPointReward {self.id} {self.status}>'
