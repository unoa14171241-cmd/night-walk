# app/models/store_plan.py
"""店舗有料プラン契約モデル"""

from datetime import datetime, date
from ..extensions import db


class StorePlan(db.Model):
    """店舗有料プラン契約"""
    __tablename__ = 'store_plans'
    
    # プランタイプ
    # 要件: 無料/プレミアム（月額15,000円+税）
    PLAN_FREE = 'free'
    PLAN_PREMIUM = 'premium'     # 月額15,000円+税（ランキング特典、ポイントカード、優良店バッジ等）
    PLAN_BUSINESS = 'business'   # 月額30,000円+税（上位プラン：バナー枠等）
    
    # 後方互換: 旧standardはpremiumと同等扱い
    PLAN_STANDARD = 'premium'
    
    PLAN_TYPES = [PLAN_FREE, PLAN_PREMIUM, PLAN_BUSINESS]
    
    PLAN_LABELS = {
        PLAN_FREE: '無料プラン',
        PLAN_PREMIUM: 'プレミアム',
        PLAN_BUSINESS: 'ビジネス',
        'standard': 'プレミアム',  # 後方互換
    }
    
    PLAN_PRICES = {
        PLAN_FREE: 0,
        PLAN_PREMIUM: 15000,    # 15,000円（税抜）
        PLAN_BUSINESS: 30000,   # 30,000円（税抜）
        'standard': 15000,      # 後方互換
    }
    
    # プラン別の特典
    PLAN_FEATURES = {
        PLAN_FREE: [],
        PLAN_PREMIUM: [
            'search_boost',      # 検索優先表示
            'premium_badge',     # 優良店バッジ
            'job_board',         # 求人掲載
            'cast_display',      # キャスト出勤表示
            'point_card',        # ポイントカード
            'ranking_benefits',  # ランキング特典
        ],
        PLAN_BUSINESS: [
            'search_boost',      # 検索優先表示（優先度高）
            'premium_badge',     # 優良店バッジ
            'job_board',         # 求人掲載
            'cast_display',      # キャスト出勤表示
            'point_card',        # ポイントカード
            'ranking_benefits',  # ランキング特典
            'top_banner',        # トップバナー掲載権
        ],
        'standard': [            # 後方互換
            'search_boost',
            'premium_badge',
            'job_board',
            'cast_display',
            'point_card',
            'ranking_benefits',
        ],
    }
    
    # プラン説明（UI表示用）
    PLAN_DESCRIPTIONS = {
        PLAN_FREE: {
            'name': '無料プラン',
            'price_display': '¥0/月',
            'features': [
                '店舗基本情報の掲載',
                '店舗画像（詳細ページ）',
                'キャスト一覧・プロフィール管理',
            ],
            'description': 'エリア内店舗としての基本掲載。ユーザーの利便性を高めます。',
        },
        PLAN_PREMIUM: {
            'name': 'プレミアムプラン',
            'price_display': '¥15,000/月（税抜）',
            'features': [
                'ランキング特典・参加権',
                'ポイントカード機能',
                '優良店バッジの付与',
                'キャスト出勤表示（リアルタイム）',
                '検索結果で優先表示',
                '求人掲載',
            ],
            'description': '初月無料！1年継続で30%OFF。紹介で最大2ヶ月無料延長。縛りなし。',
            'trial_note': '初月無料でお試しいただけます',
        },
        PLAN_BUSINESS: {
            'name': 'ビジネスプラン',
            'price_display': '¥30,000/月（税抜）',
            'features': [
                'プレミアムの全機能',
                'トップページバナー掲載権',
                '検索結果で最優先表示',
            ],
            'description': '最大限の露出で集客力を最大化。トップバナーで圧倒的な存在感。',
        },
    }
    
    # ステータス
    STATUS_ACTIVE = 'active'
    STATUS_TRIAL = 'trial'
    STATUS_PAST_DUE = 'past_due'
    STATUS_CANCELED = 'canceled'
    STATUS_EXPIRED = 'expired'
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)
    
    plan_type = db.Column(db.String(20), nullable=False, default=PLAN_FREE, index=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_ACTIVE, index=True)
    
    # 契約期間
    starts_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ends_at = db.Column(db.DateTime)  # null = 無期限（自動更新）
    
    # 試用期間
    trial_ends_at = db.Column(db.DateTime)
    
    # Stripe連携
    stripe_subscription_id = db.Column(db.String(100), index=True)
    stripe_customer_id = db.Column(db.String(100))
    
    # 請求情報
    billing_cycle_anchor = db.Column(db.DateTime)  # 請求サイクル基準日
    current_period_start = db.Column(db.DateTime)
    current_period_end = db.Column(db.DateTime)
    
    # メタデータ
    extra_data = db.Column(db.JSON)
    
    # 監査情報
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    canceled_at = db.Column(db.DateTime)
    
    # リレーション
    shop = db.relationship('Shop', backref=db.backref('store_plan', uselist=False))
    
    @property
    def plan_label(self):
        """プラン表示名"""
        return self.PLAN_LABELS.get(self.plan_type, self.plan_type)
    
    @property
    def monthly_price(self):
        """月額料金"""
        return self.PLAN_PRICES.get(self.plan_type, 0)
    
    @property
    def features(self):
        """プラン特典一覧"""
        return self.PLAN_FEATURES.get(self.plan_type, [])
    
    @property
    def is_active(self):
        """有効なプランかどうか"""
        if self.status not in [self.STATUS_ACTIVE, self.STATUS_TRIAL]:
            return False
        
        now = datetime.utcnow()
        if self.ends_at and now > self.ends_at:
            return False
        
        return True
    
    @property
    def is_paid_plan(self):
        """有料プランかどうか"""
        return self.plan_type in [self.PLAN_STANDARD, self.PLAN_PREMIUM]
    
    @property
    def is_trial(self):
        """試用期間中かどうか"""
        if self.status != self.STATUS_TRIAL:
            return False
        if not self.trial_ends_at:
            return False
        return datetime.utcnow() < self.trial_ends_at
    
    @property
    def days_until_trial_ends(self):
        """試用期間終了までの日数"""
        if not self.trial_ends_at:
            return None
        delta = self.trial_ends_at - datetime.utcnow()
        return max(0, delta.days)
    
    @property
    def has_feature(self):
        """特典チェック用のヘルパー"""
        features = set(self.features)
        
        class FeatureChecker:
            def __init__(self, features_set):
                self._features = features_set
            
            def __getattr__(self, name):
                return name in self._features
        
        return FeatureChecker(features)
    
    def has_entitlement(self, placement_type):
        """指定の広告権利を持っているか"""
        return placement_type in self.features
    
    @classmethod
    def get_or_create_free(cls, shop_id, user_id=None):
        """無料プランを取得または作成"""
        plan = cls.query.filter_by(shop_id=shop_id).first()
        if not plan:
            plan = cls(
                shop_id=shop_id,
                plan_type=cls.PLAN_FREE,
                status=cls.STATUS_ACTIVE,
                starts_at=datetime.utcnow(),
                created_by=user_id
            )
            db.session.add(plan)
        return plan
    
    @classmethod
    def get_active_paid_plans(cls):
        """有効な有料プランを取得"""
        return cls.query.filter(
            cls.plan_type.in_([cls.PLAN_STANDARD, cls.PLAN_PREMIUM]),
            cls.status.in_([cls.STATUS_ACTIVE, cls.STATUS_TRIAL])
        ).all()
    
    def upgrade(self, new_plan_type, user_id=None):
        """プランアップグレード"""
        if new_plan_type not in self.PLAN_TYPES:
            raise ValueError(f'Invalid plan type: {new_plan_type}')
        
        old_plan_type = self.plan_type
        self.plan_type = new_plan_type
        self.updated_at = datetime.utcnow()
        
        # メタデータに履歴を記録
        meta = self.extra_data or {}
        history = meta.get('upgrade_history', [])
        history.append({
            'from': old_plan_type,
            'to': new_plan_type,
            'at': datetime.utcnow().isoformat(),
            'by': user_id
        })
        meta['upgrade_history'] = history
        self.extra_data = meta
        
        return self
    
    def cancel(self, user_id=None, reason=None):
        """プランキャンセル"""
        self.status = self.STATUS_CANCELED
        self.canceled_at = datetime.utcnow()
        
        meta = self.extra_data or {}
        meta['cancellation_reason'] = reason
        meta['canceled_by'] = user_id
        self.extra_data = meta
    
    def sync_entitlements(self, user_id=None):
        """
        プランに基づいて広告権利を同期
        プラン変更時に呼び出す
        """
        from .ad_entitlement import AdEntitlement, AdPlacement
        
        if not self.is_active:
            # プラン無効時は関連権利を無効化
            entitlements = AdEntitlement.query.filter_by(
                target_type='shop',
                target_id=self.shop_id,
                source_type=AdEntitlement.SOURCE_PLAN,
                source_id=self.id,
                is_active=True
            ).all()
            
            for ent in entitlements:
                ent.deactivate(user_id, 'Plan canceled or expired')
            
            return
        
        # プラン特典に基づいて権利を付与
        for feature in self.features:
            AdEntitlement.create_from_plan(self, feature, user_id)
        
        # プラン外の特典は無効化
        current_features = set(self.features)
        existing_entitlements = AdEntitlement.query.filter_by(
            target_type='shop',
            target_id=self.shop_id,
            source_type=AdEntitlement.SOURCE_PLAN,
            source_id=self.id,
            is_active=True
        ).all()
        
        for ent in existing_entitlements:
            if ent.placement_type not in current_features:
                ent.deactivate(user_id, 'Feature not in current plan')
    
    def __repr__(self):
        return f'<StorePlan shop={self.shop_id} type={self.plan_type}>'


class StorePlanHistory(db.Model):
    """店舗プラン変更履歴"""
    __tablename__ = 'store_plan_history'
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('store_plans.id', ondelete='SET NULL'))
    
    action = db.Column(db.String(20), nullable=False)  # 'created', 'upgraded', 'downgraded', 'canceled', 'renewed'
    from_plan_type = db.Column(db.String(20))
    to_plan_type = db.Column(db.String(20))
    
    # 金額情報
    amount = db.Column(db.Integer)
    
    # 監査
    performed_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    performed_at = db.Column(db.DateTime, default=datetime.utcnow)
    note = db.Column(db.Text)
    
    @classmethod
    def log(cls, shop_id, action, plan_id=None, from_plan=None, to_plan=None, 
            amount=None, user_id=None, note=None):
        """履歴を記録"""
        history = cls(
            shop_id=shop_id,
            plan_id=plan_id,
            action=action,
            from_plan_type=from_plan,
            to_plan_type=to_plan,
            amount=amount,
            performed_by=user_id,
            note=note
        )
        db.session.add(history)
        return history
    
    def __repr__(self):
        return f'<StorePlanHistory shop={self.shop_id} {self.action}>'
