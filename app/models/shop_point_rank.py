# app/models/shop_point_rank.py
"""店舗スタンプカード ランク制度モデル"""

from datetime import datetime
from ..extensions import db


class ShopPointRank(db.Model):
    """店舗スタンプカードのランク定義"""
    __tablename__ = 'shop_point_ranks'

    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)

    rank_name = db.Column(db.String(50), nullable=False)
    rank_level = db.Column(db.Integer, nullable=False, default=0)
    min_total_points = db.Column(db.Integer, nullable=False)     # 昇格に必要な累計来店数

    # ランク特典
    point_multiplier = db.Column(db.Float, default=1.0)
    reward_discount_percent = db.Column(db.Integer, default=0)
    bonus_description = db.Column(db.String(200))                # 店舗が自由入力する特典説明

    # デザイン（テンプレートと連動）
    rank_color = db.Column(db.String(20), default='#6366f1')
    rank_icon = db.Column(db.String(10), default='')
    # カードテンプレート: 'bronze', 'silver', 'gold', 'platinum'
    card_template = db.Column(db.String(30), default='bronze')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # リレーション
    shop = db.relationship('Shop', backref=db.backref('point_ranks', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('shop_id', 'rank_level', name='uq_shop_rank_level'),
        db.Index('ix_shop_rank_threshold', 'shop_id', 'min_total_points'),
    )

    # デフォルトランクプリセット（来店回数ベース）
    DEFAULT_RANKS = [
        {
            'rank_name': 'ブロンズ',
            'rank_level': 1,
            'min_total_points': 0,       # 初回から
            'point_multiplier': 1.0,
            'rank_icon': '',
            'rank_color': '#CD7F32',
            'card_template': 'bronze',
            'bonus_description': '',
        },
        {
            'rank_name': 'シルバー',
            'rank_level': 2,
            'min_total_points': 10,      # 10回来店
            'point_multiplier': 1.0,
            'rank_icon': '',
            'rank_color': '#C0C0C0',
            'card_template': 'silver',
            'bonus_description': '',
        },
        {
            'rank_name': 'ゴールド',
            'rank_level': 3,
            'min_total_points': 30,      # 30回来店
            'point_multiplier': 1.0,
            'rank_icon': '',
            'rank_color': '#FFD700',
            'card_template': 'gold',
            'bonus_description': '',
        },
        {
            'rank_name': 'プラチナ',
            'rank_level': 4,
            'min_total_points': 50,      # 50回来店
            'point_multiplier': 1.0,
            'rank_icon': '',
            'rank_color': '#E5E4E2',
            'card_template': 'platinum',
            'bonus_description': '',
        },
    ]

    @classmethod
    def get_ranks_by_shop(cls, shop_id):
        """店舗のランク定義をレベル順で取得"""
        return cls.query.filter_by(shop_id=shop_id).order_by(cls.rank_level).all()

    @classmethod
    def get_rank_for_visits(cls, shop_id, visit_count):
        """来店回数に該当する最高ランクを取得"""
        return cls.query.filter(
            cls.shop_id == shop_id,
            cls.min_total_points <= visit_count
        ).order_by(cls.rank_level.desc()).first()

    # 後方互換エイリアス
    get_rank_for_points = get_rank_for_visits

    @classmethod
    def create_default_ranks(cls, shop_id):
        """デフォルトランクを一括作成"""
        ranks = []
        for rank_data in cls.DEFAULT_RANKS:
            rank = cls(shop_id=shop_id, **rank_data)
            db.session.add(rank)
            ranks.append(rank)
        return ranks

    def __repr__(self):
        return f'<ShopPointRank {self.rank_name} lv={self.rank_level} shop={self.shop_id}>'


class CustomerShopRank(db.Model):
    """顧客の店舗別ランク（現在＋履歴）"""
    __tablename__ = 'customer_shop_ranks'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id', ondelete='CASCADE'), nullable=False, index=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)
    rank_id = db.Column(db.Integer, db.ForeignKey('shop_point_ranks.id', ondelete='SET NULL'), index=True)

    rank_name = db.Column(db.String(50))
    rank_level = db.Column(db.Integer, default=0)
    rank_icon = db.Column(db.String(10))

    promoted_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_current = db.Column(db.Boolean, default=True, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # リレーション
    customer = db.relationship('Customer', backref=db.backref('shop_ranks', lazy='dynamic'))
    shop = db.relationship('Shop', backref=db.backref('customer_ranks', lazy='dynamic'))
    rank = db.relationship('ShopPointRank')

    __table_args__ = (
        db.Index('ix_customer_shop_rank_current', 'customer_id', 'shop_id', 'is_current'),
    )

    @classmethod
    def get_current_rank(cls, customer_id, shop_id):
        """顧客の現在のランクを取得"""
        return cls.query.filter_by(
            customer_id=customer_id,
            shop_id=shop_id,
            is_current=True
        ).first()

    def __repr__(self):
        return f'<CustomerShopRank customer={self.customer_id} shop={self.shop_id} rank={self.rank_name}>'
