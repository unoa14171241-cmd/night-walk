# app/models/ranking.py
"""キャストランキング関連モデル"""

from datetime import datetime, date
from calendar import monthrange
from ..extensions import db


# エリア定義（都道府県コード対応）
AREA_DEFINITIONS = {
    'okayama': {
        'code': '33',
        'name': '岡山',
        'prefecture': '岡山県',
        'is_active': True,
    },
    'hiroshima': {
        'code': '34',
        'name': '広島',
        'prefecture': '広島県',
        'is_active': False,  # 将来対応
    },
}


class CastPageView(db.Model):
    """キャストページビュー記録（ユニークPV用）"""
    __tablename__ = 'cast_page_views'
    
    id = db.Column(db.Integer, primary_key=True)
    cast_id = db.Column(db.Integer, db.ForeignKey('casts.id', ondelete='CASCADE'), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id', ondelete='SET NULL'), index=True)  # ログインユーザー
    session_id = db.Column(db.String(64), index=True)  # 非ログインユーザー用
    
    # PV発生時刻
    viewed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # 追加情報
    ip_address = db.Column(db.String(45))  # IPv6対応
    user_agent = db.Column(db.String(255))
    
    # リレーション
    cast = db.relationship('Cast', backref=db.backref('page_views', lazy='dynamic'))
    customer = db.relationship('Customer', backref=db.backref('cast_views', lazy='dynamic'))
    
    # 24時間以内の重複チェック用インデックス
    __table_args__ = (
        db.Index('ix_cast_pv_customer', 'cast_id', 'customer_id', 'viewed_at'),
        db.Index('ix_cast_pv_session', 'cast_id', 'session_id', 'viewed_at'),
    )
    
    @classmethod
    def can_count_view(cls, cast_id, customer_id=None, session_id=None, hours=24):
        """
        24時間以内に同一ユーザーがPVカウント済みか確認
        Returns: True if new view should be counted
        """
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        query = cls.query.filter(
            cls.cast_id == cast_id,
            cls.viewed_at > cutoff
        )
        
        if customer_id:
            return not query.filter(cls.customer_id == customer_id).first()
        elif session_id:
            return not query.filter(cls.session_id == session_id).first()
        
        return True  # 識別不可の場合はカウント
    
    @classmethod
    def record_view(cls, cast_id, customer_id=None, session_id=None, ip_address=None, user_agent=None):
        """
        PVを記録（24時間以内の重複はカウントしない）
        Returns: True if new view was recorded
        """
        if not cls.can_count_view(cast_id, customer_id, session_id):
            return False
        
        view = cls(
            cast_id=cast_id,
            customer_id=customer_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent[:255] if user_agent else None
        )
        db.session.add(view)
        return True
    
    @classmethod
    def get_unique_count(cls, cast_id, start_date, end_date):
        """指定期間のユニークPV数を取得"""
        # customer_idベースのユニーク数 + session_idベースのユニーク数
        customer_count = db.session.query(
            db.func.count(db.distinct(cls.customer_id))
        ).filter(
            cls.cast_id == cast_id,
            cls.viewed_at >= start_date,
            cls.viewed_at < end_date,
            cls.customer_id != None
        ).scalar() or 0
        
        session_count = db.session.query(
            db.func.count(db.distinct(cls.session_id))
        ).filter(
            cls.cast_id == cast_id,
            cls.viewed_at >= start_date,
            cls.viewed_at < end_date,
            cls.customer_id == None,
            cls.session_id != None
        ).scalar() or 0
        
        return customer_count + session_count
    
    def __repr__(self):
        return f'<CastPageView cast={self.cast_id} at {self.viewed_at}>'


class CastMonthlyRanking(db.Model):
    """月次キャストランキング"""
    __tablename__ = 'cast_monthly_rankings'
    
    id = db.Column(db.Integer, primary_key=True)
    cast_id = db.Column(db.Integer, db.ForeignKey('casts.id', ondelete='CASCADE'), nullable=False, index=True)
    area = db.Column(db.String(50), nullable=False, index=True)  # エリアキー（okayama, hiroshimaなど）
    
    # 集計期間
    year = db.Column(db.Integer, nullable=False, index=True)
    month = db.Column(db.Integer, nullable=False, index=True)
    
    # スコア内訳（生データ）
    pv_count = db.Column(db.Integer, default=0)           # ユニークPV数
    gift_points = db.Column(db.Integer, default=0)        # ギフト合計ポイント
    gift_count = db.Column(db.Integer, default=0)         # ギフト件数
    
    # 計算済みスコア（係数適用後）
    pv_score = db.Column(db.Float, default=0)             # pv_weight × pv_count
    gift_score = db.Column(db.Float, default=0)           # gift_weight × gift_points
    total_score = db.Column(db.Float, default=0)          # 合計スコア
    
    # ランキング
    rank = db.Column(db.Integer, index=True)              # 順位（1〜）
    previous_rank = db.Column(db.Integer)                 # 前月順位（変動表示用）
    
    # ステータス
    is_finalized = db.Column(db.Boolean, default=False, index=True)  # 確定済み
    finalized_at = db.Column(db.DateTime)
    
    # 管理者による上書き
    is_overridden = db.Column(db.Boolean, default=False)  # 強制差し替え
    override_reason = db.Column(db.String(255))           # 差し替え理由
    overridden_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    overridden_at = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーション
    cast = db.relationship('Cast', backref=db.backref('monthly_rankings', lazy='dynamic'))
    
    __table_args__ = (
        db.UniqueConstraint('cast_id', 'area', 'year', 'month', name='uq_cast_ranking_period'),
        db.Index('ix_ranking_period_area', 'year', 'month', 'area', 'rank'),
    )
    
    @property
    def period_display(self):
        """期間表示"""
        return f'{self.year}年{self.month}月'
    
    @property
    def area_name(self):
        """エリア表示名"""
        area_def = AREA_DEFINITIONS.get(self.area, {})
        return area_def.get('name', self.area)
    
    @property
    def rank_change(self):
        """順位変動（↑↓→）"""
        if not self.previous_rank or not self.rank:
            return None
        diff = self.previous_rank - self.rank
        if diff > 0:
            return f'↑{diff}'
        elif diff < 0:
            return f'↓{abs(diff)}'
        return '→'
    
    @classmethod
    def get_ranking(cls, area, year, month, limit=100, finalized_only=True):
        """エリア別ランキング取得"""
        query = cls.query.filter(
            cls.area == area,
            cls.year == year,
            cls.month == month
        )
        if finalized_only:
            query = query.filter(cls.is_finalized == True)
        
        return query.order_by(cls.rank).limit(limit).all()
    
    @classmethod
    def get_top1(cls, area, year, month):
        """エリアTOP1を取得"""
        return cls.query.filter(
            cls.area == area,
            cls.year == year,
            cls.month == month,
            cls.rank == 1,
            cls.is_finalized == True
        ).first()
    
    def __repr__(self):
        return f'<CastMonthlyRanking {self.area} {self.year}/{self.month} #{self.rank}>'


class CastBadgeHistory(db.Model):
    """キャストバッジ・特典履歴"""
    __tablename__ = 'cast_badge_history'
    
    # バッジタイプ
    BADGE_TOP1 = 'area_top1'
    BADGE_TOP3 = 'area_top3'
    BADGE_TOP10 = 'area_top10'
    
    BADGE_LABELS = {
        BADGE_TOP1: 'エリアTOP1',
        BADGE_TOP3: 'エリアTOP3',
        BADGE_TOP10: 'エリアTOP10',
    }
    
    BADGE_COLORS = {
        BADGE_TOP1: 'gold',
        BADGE_TOP3: 'silver',
        BADGE_TOP10: 'bronze',
    }
    
    id = db.Column(db.Integer, primary_key=True)
    cast_id = db.Column(db.Integer, db.ForeignKey('casts.id', ondelete='CASCADE'), nullable=False, index=True)
    ranking_id = db.Column(db.Integer, db.ForeignKey('cast_monthly_rankings.id', ondelete='SET NULL'))
    
    badge_type = db.Column(db.String(20), nullable=False)  # area_top1, area_top3, area_top10
    area = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    
    # 有効期間（翌月1日〜月末）
    valid_from = db.Column(db.Date, nullable=False)
    valid_until = db.Column(db.Date, nullable=False)
    
    # 特典発送情報（TOP1のみ）
    prize_name = db.Column(db.String(100))                 # 特典名
    prize_shipped = db.Column(db.Boolean, default=False)
    shipping_name = db.Column(db.String(100))              # 配送先氏名
    shipping_postal_code = db.Column(db.String(10))
    shipping_address = db.Column(db.Text)
    shipping_phone = db.Column(db.String(20))
    address_submitted_at = db.Column(db.DateTime)          # 住所入力日時
    shipped_at = db.Column(db.DateTime)
    tracking_number = db.Column(db.String(50))             # 追跡番号
    
    # 通知
    notified_at = db.Column(db.DateTime)                   # 獲得通知送信日時
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーション
    cast = db.relationship('Cast', backref=db.backref('badges', lazy='dynamic'))
    ranking = db.relationship('CastMonthlyRanking', backref='badges')
    
    @property
    def badge_label(self):
        return self.BADGE_LABELS.get(self.badge_type, self.badge_type)
    
    @property
    def badge_color(self):
        return self.BADGE_COLORS.get(self.badge_type, 'gray')
    
    @property
    def area_name(self):
        area_def = AREA_DEFINITIONS.get(self.area, {})
        return area_def.get('name', self.area)
    
    @property
    def is_valid(self):
        """現在有効かどうか"""
        today = date.today()
        return self.valid_from <= today <= self.valid_until
    
    @property
    def is_top1(self):
        return self.badge_type == self.BADGE_TOP1
    
    @classmethod
    def get_active_badges(cls, cast_id):
        """現在有効なバッジを取得"""
        today = date.today()
        return cls.query.filter(
            cls.cast_id == cast_id,
            cls.valid_from <= today,
            cls.valid_until >= today
        ).order_by(cls.badge_type).all()
    
    @classmethod
    def get_history(cls, cast_id, limit=12):
        """バッジ履歴を取得"""
        return cls.query.filter(
            cls.cast_id == cast_id
        ).order_by(cls.year.desc(), cls.month.desc()).limit(limit).all()
    
    @classmethod
    def create_badge(cls, ranking):
        """ランキング結果からバッジを作成"""
        if not ranking.rank or ranking.rank > 10:
            return None
        
        # バッジタイプ決定
        if ranking.rank == 1:
            badge_type = cls.BADGE_TOP1
        elif ranking.rank <= 3:
            badge_type = cls.BADGE_TOP3
        else:
            badge_type = cls.BADGE_TOP10
        
        # 有効期間計算（翌月1日〜月末）
        if ranking.month == 12:
            valid_from = date(ranking.year + 1, 1, 1)
            valid_until = date(ranking.year + 1, 1, 31)
        else:
            valid_from = date(ranking.year, ranking.month + 1, 1)
            _, last_day = monthrange(ranking.year, ranking.month + 1)
            valid_until = date(ranking.year, ranking.month + 1, last_day)
        
        badge = cls(
            cast_id=ranking.cast_id,
            ranking_id=ranking.id,
            badge_type=badge_type,
            area=ranking.area,
            year=ranking.year,
            month=ranking.month,
            valid_from=valid_from,
            valid_until=valid_until
        )
        
        return badge
    
    def __repr__(self):
        return f'<CastBadgeHistory {self.cast_id} {self.badge_type} {self.year}/{self.month}>'


class RankingConfig(db.Model):
    """ランキング設定（システム設定）"""
    __tablename__ = 'ranking_config'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False, index=True)
    value = db.Column(db.String(255), nullable=False)
    value_type = db.Column(db.String(20), default='string')  # string, int, float, bool
    description = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    
    # デフォルト設定
    DEFAULTS = {
        'pv_weight': ('1.0', 'float', 'PVスコア係数'),
        'gift_weight': ('1.0', 'float', 'ギフトスコア係数'),
        'ranking_top_count': ('100', 'int', '表示ランキング数'),
        'pv_unique_hours': ('24', 'int', 'PVユニーク判定時間（時間）'),
    }
    
    @classmethod
    def get(cls, key, default=None):
        """設定値を取得"""
        config = cls.query.filter_by(key=key).first()
        if config:
            return config.typed_value
        
        # デフォルト値
        if key in cls.DEFAULTS:
            val, val_type, _ = cls.DEFAULTS[key]
            return cls._convert_value(val, val_type)
        
        return default
    
    @classmethod
    def set(cls, key, value, user_id=None):
        """設定値を保存"""
        config = cls.query.filter_by(key=key).first()
        if not config:
            val_type = 'string'
            description = None
            if key in cls.DEFAULTS:
                _, val_type, description = cls.DEFAULTS[key]
            
            config = cls(
                key=key,
                value=str(value),
                value_type=val_type,
                description=description,
                updated_by=user_id
            )
            db.session.add(config)
        else:
            config.value = str(value)
            config.updated_by = user_id
        
        return config
    
    @classmethod
    def get_all(cls):
        """全設定を取得（デフォルト含む）"""
        configs = {}
        
        # デフォルト値をセット
        for key, (val, val_type, desc) in cls.DEFAULTS.items():
            configs[key] = {
                'value': cls._convert_value(val, val_type),
                'value_type': val_type,
                'description': desc,
                'is_default': True
            }
        
        # DB値で上書き
        for config in cls.query.all():
            configs[config.key] = {
                'value': config.typed_value,
                'value_type': config.value_type,
                'description': config.description,
                'is_default': False,
                'updated_at': config.updated_at
            }
        
        return configs
    
    @property
    def typed_value(self):
        """型変換された値"""
        return self._convert_value(self.value, self.value_type)
    
    @staticmethod
    def _convert_value(value, value_type):
        """値を指定型に変換"""
        if value_type == 'int':
            return int(value)
        elif value_type == 'float':
            return float(value)
        elif value_type == 'bool':
            return value.lower() in ('true', '1', 'yes')
        return value
    
    def __repr__(self):
        return f'<RankingConfig {self.key}={self.value}>'
