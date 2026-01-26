# app/models/ad_entitlement.py
"""広告権利・広告枠管理モデル"""

from datetime import datetime, date
from ..extensions import db


class AdPlacement(db.Model):
    """広告枠定義マスタ"""
    __tablename__ = 'ad_placements'
    
    # 枠タイプ定義
    TYPE_TOP_BANNER = 'top_banner'           # エリアトップバナー
    TYPE_SEARCH_BOOST = 'search_boost'       # 検索優先表示
    TYPE_PREMIUM_BADGE = 'premium_badge'     # 優良店バッジ
    TYPE_TOP_BADGE = 'top_badge'             # TOP1/2/3バッジ
    TYPE_PLATINUM_PROFILE = 'platinum'       # プラチナプロフィール（キャスト装飾）
    TYPE_JOB_BOARD = 'job_board'             # 求人掲載権利
    TYPE_CAST_DISPLAY = 'cast_display'       # キャスト出勤表示権利
    TYPE_INLINE_AD = 'inline_ad'             # 一覧内広告
    
    PLACEMENT_TYPES = [
        TYPE_TOP_BANNER, TYPE_SEARCH_BOOST, TYPE_PREMIUM_BADGE,
        TYPE_TOP_BADGE, TYPE_PLATINUM_PROFILE, TYPE_JOB_BOARD,
        TYPE_CAST_DISPLAY, TYPE_INLINE_AD
    ]
    
    PLACEMENT_LABELS = {
        TYPE_TOP_BANNER: 'エリアトップバナー',
        TYPE_SEARCH_BOOST: '検索優先表示',
        TYPE_PREMIUM_BADGE: '優良店バッジ',
        TYPE_TOP_BADGE: 'TOPバッジ',
        TYPE_PLATINUM_PROFILE: 'プラチナプロフィール',
        TYPE_JOB_BOARD: '求人掲載',
        TYPE_CAST_DISPLAY: 'キャスト出勤表示',
        TYPE_INLINE_AD: '一覧内広告',
    }
    
    id = db.Column(db.Integer, primary_key=True)
    placement_type = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    
    # 枠の制限
    max_slots = db.Column(db.Integer, default=1)  # 同時表示可能数（0=無制限）
    target_types = db.Column(db.String(50), default='shop')  # 対象: 'shop', 'cast', 'both'
    
    # 料金情報（参考）
    monthly_price = db.Column(db.Integer)  # 月額料金（円）
    
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def label(self):
        """表示名"""
        return self.PLACEMENT_LABELS.get(self.placement_type, self.name)
    
    @classmethod
    def get_by_type(cls, placement_type):
        """タイプで取得"""
        return cls.query.filter_by(placement_type=placement_type, is_active=True).first()
    
    @classmethod
    def get_all_active(cls):
        """有効な枠一覧"""
        return cls.query.filter_by(is_active=True).order_by(cls.placement_type).all()
    
    @classmethod
    def ensure_defaults(cls):
        """デフォルト枠を初期化"""
        defaults = [
            (cls.TYPE_TOP_BANNER, 'エリアトップバナー', 'トップページ上部のメインバナー枠', 3, 'both'),
            (cls.TYPE_SEARCH_BOOST, '検索優先表示', '検索結果での優先表示権利', 0, 'shop'),
            (cls.TYPE_PREMIUM_BADGE, '優良店バッジ', '有料プラン加入店舗のバッジ', 0, 'shop'),
            (cls.TYPE_TOP_BADGE, 'TOPバッジ', 'ランキングTOP入賞バッジ', 0, 'both'),
            (cls.TYPE_PLATINUM_PROFILE, 'プラチナプロフィール', 'キャストプロフィール装飾', 0, 'cast'),
            (cls.TYPE_JOB_BOARD, '求人掲載', '求人情報掲載権利', 0, 'shop'),
            (cls.TYPE_CAST_DISPLAY, 'キャスト出勤表示', 'リアルタイム出勤表示権利', 0, 'shop'),
            (cls.TYPE_INLINE_AD, '一覧内広告', '店舗一覧内に表示される広告枠', 5, 'both'),
        ]
        
        for ptype, name, desc, max_slots, target_types in defaults:
            existing = cls.query.filter_by(placement_type=ptype).first()
            if not existing:
                placement = cls(
                    placement_type=ptype,
                    name=name,
                    description=desc,
                    max_slots=max_slots,
                    target_types=target_types
                )
                db.session.add(placement)
        
        db.session.commit()
    
    def __repr__(self):
        return f'<AdPlacement {self.placement_type}>'


class AdEntitlement(db.Model):
    """広告権利（誰がいつどの枠に出せるか - 唯一の真実）"""
    __tablename__ = 'ad_entitlements'
    
    # ソースタイプ（権利の発生源）
    SOURCE_PLAN = 'plan'           # 有料プラン契約
    SOURCE_RANKING = 'ranking'     # ランキング特典（自動付与）
    SOURCE_MANUAL = 'manual'       # 運営手動付与
    SOURCE_PROMOTION = 'promotion' # キャンペーン
    
    SOURCE_TYPES = [SOURCE_PLAN, SOURCE_RANKING, SOURCE_MANUAL, SOURCE_PROMOTION]
    
    SOURCE_LABELS = {
        SOURCE_PLAN: '有料プラン',
        SOURCE_RANKING: 'ランキング特典',
        SOURCE_MANUAL: '手動付与',
        SOURCE_PROMOTION: 'キャンペーン',
    }
    
    # ターゲットタイプ
    TARGET_SHOP = 'shop'
    TARGET_CAST = 'cast'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # 対象（店舗またはキャスト）
    target_type = db.Column(db.String(20), nullable=False, index=True)  # 'shop' or 'cast'
    target_id = db.Column(db.Integer, nullable=False, index=True)
    
    # 枠情報
    placement_type = db.Column(db.String(50), nullable=False, index=True)
    area = db.Column(db.String(50), index=True)  # エリア限定の場合（null=全エリア）
    
    # 優先度（大きいほど優先表示）
    priority = db.Column(db.Integer, default=0, index=True)
    
    # 期間制御（必須）
    starts_at = db.Column(db.DateTime, nullable=False, index=True)
    ends_at = db.Column(db.DateTime, nullable=False, index=True)
    
    # 権利の発生源
    source_type = db.Column(db.String(20), nullable=False, index=True)
    source_id = db.Column(db.Integer)  # ranking_id, plan_id, promotion_id など
    
    # メタデータ（バッジランク、装飾レベル、バナー画像URL等）
    extra_data = db.Column(db.JSON)
    
    # ステータス
    is_active = db.Column(db.Boolean, default=True, index=True)
    
    # 監査情報
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーション
    creator = db.relationship('User', foreign_keys=[created_by])
    updater = db.relationship('User', foreign_keys=[updated_by])
    
    # インデックス
    __table_args__ = (
        db.Index('ix_entitlement_target', 'target_type', 'target_id'),
        db.Index('ix_entitlement_period', 'starts_at', 'ends_at'),
        db.Index('ix_entitlement_active_placement', 'is_active', 'placement_type', 'starts_at', 'ends_at'),
    )
    
    @property
    def source_label(self):
        """ソース表示名"""
        return self.SOURCE_LABELS.get(self.source_type, self.source_type)
    
    @property
    def placement_label(self):
        """枠表示名"""
        return AdPlacement.PLACEMENT_LABELS.get(self.placement_type, self.placement_type)
    
    @property
    def is_valid(self):
        """現在有効かどうか"""
        if not self.is_active:
            return False
        now = datetime.utcnow()
        return self.starts_at <= now <= self.ends_at
    
    @property
    def is_expired(self):
        """期限切れかどうか"""
        return datetime.utcnow() > self.ends_at
    
    @property
    def is_future(self):
        """将来開始かどうか"""
        return datetime.utcnow() < self.starts_at
    
    @property
    def days_remaining(self):
        """残り日数"""
        if self.is_expired:
            return 0
        delta = self.ends_at - datetime.utcnow()
        return max(0, delta.days)
    
    @property
    def target(self):
        """対象エンティティを取得"""
        if self.target_type == self.TARGET_SHOP:
            from .shop import Shop
            return Shop.query.get(self.target_id)
        elif self.target_type == self.TARGET_CAST:
            from .gift import Cast
            return Cast.query.get(self.target_id)
        return None
    
    @classmethod
    def get_active(cls, placement_type=None, target_type=None, target_id=None, area=None):
        """
        現在有効な権利を取得
        
        Args:
            placement_type: 枠タイプでフィルタ
            target_type: 対象タイプでフィルタ ('shop' or 'cast')
            target_id: 対象IDでフィルタ
            area: エリアでフィルタ
        """
        now = datetime.utcnow()
        query = cls.query.filter(
            cls.is_active == True,
            cls.starts_at <= now,
            cls.ends_at >= now
        )
        
        if placement_type:
            query = query.filter(cls.placement_type == placement_type)
        
        if target_type:
            query = query.filter(cls.target_type == target_type)
        
        if target_id is not None:
            query = query.filter(cls.target_id == target_id)
        
        if area:
            # エリア指定がある場合、そのエリアまたは全エリア対象を取得
            query = query.filter(
                (cls.area == area) | (cls.area == None)
            )
        
        return query.order_by(cls.priority.desc(), cls.created_at.desc()).all()
    
    @classmethod
    def get_for_target(cls, target_type, target_id, active_only=True):
        """対象の全権利を取得"""
        query = cls.query.filter(
            cls.target_type == target_type,
            cls.target_id == target_id
        )
        
        if active_only:
            now = datetime.utcnow()
            query = query.filter(
                cls.is_active == True,
                cls.starts_at <= now,
                cls.ends_at >= now
            )
        
        return query.order_by(cls.ends_at.desc()).all()
    
    @classmethod
    def has_entitlement(cls, target_type, target_id, placement_type, area=None):
        """指定の権利を持っているか確認"""
        entitlements = cls.get_active(
            placement_type=placement_type,
            target_type=target_type,
            target_id=target_id,
            area=area
        )
        return len(entitlements) > 0
    
    @classmethod
    def get_top_banner_targets(cls, area):
        """エリアトップバナーの対象を取得"""
        entitlements = cls.get_active(
            placement_type=AdPlacement.TYPE_TOP_BANNER,
            area=area
        )
        
        results = []
        for ent in entitlements:
            target = ent.target
            if target:
                results.append({
                    'entitlement': ent,
                    'target': target,
                    'target_type': ent.target_type,
                    'extra_data': ent.extra_data or {}
                })
        
        return results
    
    @classmethod
    def get_search_boost_shop_ids(cls, area=None):
        """検索優先表示の店舗IDと優先度を取得"""
        entitlements = cls.get_active(
            placement_type=AdPlacement.TYPE_SEARCH_BOOST,
            target_type=cls.TARGET_SHOP,
            area=area
        )
        
        return {ent.target_id: ent.priority for ent in entitlements}
    
    @classmethod
    def create_from_ranking(cls, ranking, placement_type, starts_at, ends_at, metadata=None, user_id=None):
        """ランキング結果から権利を作成"""
        from .ranking import CastMonthlyRanking
        
        # 既存チェック
        existing = cls.query.filter_by(
            target_type=cls.TARGET_CAST,
            target_id=ranking.cast_id,
            placement_type=placement_type,
            source_type=cls.SOURCE_RANKING,
            source_id=ranking.id
        ).first()
        
        if existing:
            return existing
        
        # 優先度決定（ランク順）
        priority = 100 - (ranking.rank or 100)
        
        entitlement = cls(
            target_type=cls.TARGET_CAST,
            target_id=ranking.cast_id,
            placement_type=placement_type,
            area=ranking.area,
            priority=priority,
            starts_at=starts_at,
            ends_at=ends_at,
            source_type=cls.SOURCE_RANKING,
            source_id=ranking.id,
            extra_data=metadata or {'rank': ranking.rank, 'year': ranking.year, 'month': ranking.month},
            is_active=True,
            created_by=user_id
        )
        
        db.session.add(entitlement)
        return entitlement
    
    @classmethod
    def create_from_plan(cls, plan, placement_type, user_id=None):
        """有料プランから権利を作成"""
        # 既存チェック（同一プランからの同一枠）
        existing = cls.query.filter_by(
            target_type=cls.TARGET_SHOP,
            target_id=plan.shop_id,
            placement_type=placement_type,
            source_type=cls.SOURCE_PLAN,
            source_id=plan.id,
            is_active=True
        ).first()
        
        if existing:
            # 期間更新
            existing.ends_at = plan.ends_at or datetime(2099, 12, 31)
            existing.updated_by = user_id
            return existing
        
        # 優先度決定（プランタイプ順）
        priority_map = {
            'premium': 50,
            'standard': 30,
            'free': 0
        }
        priority = priority_map.get(plan.plan_type, 0)
        
        entitlement = cls(
            target_type=cls.TARGET_SHOP,
            target_id=plan.shop_id,
            placement_type=placement_type,
            area=None,  # 全エリア
            priority=priority,
            starts_at=plan.starts_at,
            ends_at=plan.ends_at or datetime(2099, 12, 31),
            source_type=cls.SOURCE_PLAN,
            source_id=plan.id,
            extra_data={'plan_type': plan.plan_type},
            is_active=True,
            created_by=user_id
        )
        
        db.session.add(entitlement)
        return entitlement
    
    def deactivate(self, user_id=None, reason=None):
        """権利を無効化"""
        self.is_active = False
        self.updated_by = user_id
        if reason:
            meta = self.extra_data or {}
            meta['deactivation_reason'] = reason
            meta['deactivated_at'] = datetime.utcnow().isoformat()
            self.extra_data = meta
    
    def __repr__(self):
        return f'<AdEntitlement {self.target_type}:{self.target_id} {self.placement_type}>'
