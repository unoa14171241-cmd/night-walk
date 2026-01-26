# app/models/shop_ranking.py
"""店舗PV・ランキング関連モデル"""

from datetime import datetime, date, timedelta
from calendar import monthrange
from ..extensions import db


class ShopPageView(db.Model):
    """店舗ページビュー記録（急上昇・ランキング計算用）"""
    __tablename__ = 'shop_page_views'
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id', ondelete='SET NULL'), index=True)
    session_id = db.Column(db.String(64), index=True)  # 非ログインユーザー用
    
    # PV発生時刻
    viewed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # 追加情報
    ip_address = db.Column(db.String(45))  # IPv6対応
    user_agent = db.Column(db.String(255))
    referrer = db.Column(db.String(500))  # 流入元
    
    # ページタイプ
    page_type = db.Column(db.String(20), default='detail')  # 'detail', 'booking', 'job'
    
    # リレーション
    shop = db.relationship('Shop', backref=db.backref('page_views', lazy='dynamic'))
    customer = db.relationship('Customer', backref=db.backref('shop_views', lazy='dynamic'))
    
    # 複合インデックス
    __table_args__ = (
        db.Index('ix_shop_pv_customer', 'shop_id', 'customer_id', 'viewed_at'),
        db.Index('ix_shop_pv_session', 'shop_id', 'session_id', 'viewed_at'),
        db.Index('ix_shop_pv_time', 'viewed_at', 'shop_id'),  # 急上昇計算用
    )
    
    @classmethod
    def can_count_view(cls, shop_id, customer_id=None, session_id=None, hours=1):
        """
        指定時間以内に同一ユーザーがPVカウント済みか確認
        急上昇計算用は1時間、ランキング用は24時間で判定
        Returns: True if new view should be counted
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        query = cls.query.filter(
            cls.shop_id == shop_id,
            cls.viewed_at > cutoff
        )
        
        if customer_id:
            return not query.filter(cls.customer_id == customer_id).first()
        elif session_id:
            return not query.filter(cls.session_id == session_id).first()
        
        return True  # 識別不可の場合はカウント
    
    @classmethod
    def record_view(cls, shop_id, customer_id=None, session_id=None, 
                    ip_address=None, user_agent=None, referrer=None, page_type='detail'):
        """
        PVを記録（1時間以内の重複はカウントしない）
        Returns: True if new view was recorded
        """
        if not cls.can_count_view(shop_id, customer_id, session_id, hours=1):
            return False
        
        view = cls(
            shop_id=shop_id,
            customer_id=customer_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent[:255] if user_agent else None,
            referrer=referrer[:500] if referrer else None,
            page_type=page_type
        )
        db.session.add(view)
        return True
    
    @classmethod
    def get_count(cls, shop_id, start_time, end_time):
        """指定期間のPV数を取得"""
        return cls.query.filter(
            cls.shop_id == shop_id,
            cls.viewed_at >= start_time,
            cls.viewed_at < end_time
        ).count()
    
    @classmethod
    def get_unique_count(cls, shop_id, start_date, end_date):
        """指定期間のユニークPV数を取得"""
        customer_count = db.session.query(
            db.func.count(db.distinct(cls.customer_id))
        ).filter(
            cls.shop_id == shop_id,
            cls.viewed_at >= start_date,
            cls.viewed_at < end_date,
            cls.customer_id != None
        ).scalar() or 0
        
        session_count = db.session.query(
            db.func.count(db.distinct(cls.session_id))
        ).filter(
            cls.shop_id == shop_id,
            cls.viewed_at >= start_date,
            cls.viewed_at < end_date,
            cls.customer_id == None,
            cls.session_id != None
        ).scalar() or 0
        
        return customer_count + session_count
    
    @classmethod
    def get_trending_data(cls, window_minutes=60, min_pv=5):
        """
        急上昇計算用データを取得
        
        Args:
            window_minutes: 比較ウィンドウ（分）
            min_pv: 最小PV閾値（ノイズ除去）
        
        Returns:
            dict: {shop_id: {'current': int, 'previous': int, 'growth_rate': float}}
        """
        now = datetime.utcnow()
        current_start = now - timedelta(minutes=window_minutes)
        previous_start = current_start - timedelta(minutes=window_minutes)
        
        # 現在のウィンドウのPV
        current_pvs = db.session.query(
            cls.shop_id,
            db.func.count(cls.id).label('count')
        ).filter(
            cls.viewed_at >= current_start,
            cls.viewed_at < now
        ).group_by(cls.shop_id).all()
        
        current_map = {row.shop_id: row.count for row in current_pvs}
        
        # 直前のウィンドウのPV
        previous_pvs = db.session.query(
            cls.shop_id,
            db.func.count(cls.id).label('count')
        ).filter(
            cls.viewed_at >= previous_start,
            cls.viewed_at < current_start
        ).group_by(cls.shop_id).all()
        
        previous_map = {row.shop_id: row.count for row in previous_pvs}
        
        # 伸び率計算
        all_shop_ids = set(current_map.keys()) | set(previous_map.keys())
        results = {}
        
        for shop_id in all_shop_ids:
            current = current_map.get(shop_id, 0)
            previous = previous_map.get(shop_id, 0)
            
            # 最小PV閾値チェック
            if current < min_pv:
                continue
            
            # 伸び率計算: (current - previous) / max(previous, 1)
            growth_rate = (current - previous) / max(previous, 1)
            
            results[shop_id] = {
                'current': current,
                'previous': previous,
                'growth_rate': growth_rate
            }
        
        return results
    
    def __repr__(self):
        return f'<ShopPageView shop={self.shop_id} at {self.viewed_at}>'


class ShopMonthlyRanking(db.Model):
    """店舗月次ランキング"""
    __tablename__ = 'shop_monthly_rankings'
    
    # ランキングタイプ
    TYPE_PV = 'pv'            # PVランキング
    TYPE_BOOKING = 'booking'  # 予約数ランキング
    TYPE_REVENUE = 'revenue'  # 売上ランキング（将来用）
    
    RANKING_TYPES = [TYPE_PV, TYPE_BOOKING, TYPE_REVENUE]
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)
    area = db.Column(db.String(50), nullable=False, index=True)  # 岡山、倉敷
    
    # ランキングタイプ
    rank_type = db.Column(db.String(20), nullable=False, default=TYPE_PV, index=True)
    
    # 集計期間
    year = db.Column(db.Integer, nullable=False, index=True)
    month = db.Column(db.Integer, nullable=False, index=True)
    
    # スコア内訳
    pv_count = db.Column(db.Integer, default=0)
    unique_pv_count = db.Column(db.Integer, default=0)
    booking_count = db.Column(db.Integer, default=0)
    
    # 計算済みスコア
    total_score = db.Column(db.Float, default=0)
    
    # ランキング
    rank = db.Column(db.Integer, index=True)
    previous_rank = db.Column(db.Integer)
    
    # ステータス
    is_finalized = db.Column(db.Boolean, default=False, index=True)
    finalized_at = db.Column(db.DateTime)
    
    # 管理者による上書き
    is_overridden = db.Column(db.Boolean, default=False)
    override_reason = db.Column(db.String(255))
    overridden_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    overridden_at = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーション
    shop = db.relationship('Shop', backref=db.backref('monthly_rankings', lazy='dynamic'))
    
    __table_args__ = (
        db.UniqueConstraint('shop_id', 'area', 'rank_type', 'year', 'month', name='uq_shop_ranking_period'),
        db.Index('ix_shop_ranking_period', 'year', 'month', 'area', 'rank_type', 'rank'),
    )
    
    @property
    def period_display(self):
        """期間表示"""
        return f'{self.year}年{self.month}月'
    
    @property
    def rank_change(self):
        """順位変動"""
        if not self.previous_rank or not self.rank:
            return None
        diff = self.previous_rank - self.rank
        if diff > 0:
            return f'↑{diff}'
        elif diff < 0:
            return f'↓{abs(diff)}'
        return '→'
    
    @classmethod
    def get_ranking(cls, area, year, month, rank_type=None, limit=100, finalized_only=True):
        """エリア別ランキング取得"""
        query = cls.query.filter(
            cls.area == area,
            cls.year == year,
            cls.month == month
        )
        
        if rank_type:
            query = query.filter(cls.rank_type == rank_type)
        else:
            query = query.filter(cls.rank_type == cls.TYPE_PV)
        
        if finalized_only:
            query = query.filter(cls.is_finalized == True)
        
        return query.order_by(cls.rank).limit(limit).all()
    
    @classmethod
    def get_top(cls, area, year, month, rank=1, rank_type=None):
        """指定順位の店舗を取得"""
        query = cls.query.filter(
            cls.area == area,
            cls.year == year,
            cls.month == month,
            cls.rank == rank,
            cls.is_finalized == True
        )
        
        if rank_type:
            query = query.filter(cls.rank_type == rank_type)
        else:
            query = query.filter(cls.rank_type == cls.TYPE_PV)
        
        return query.first()
    
    def __repr__(self):
        return f'<ShopMonthlyRanking {self.area} {self.year}/{self.month} #{self.rank}>'


class TrendingShop(db.Model):
    """急上昇店舗（キャッシュテーブル）"""
    __tablename__ = 'trending_shops'
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)
    area = db.Column(db.String(50), nullable=False, index=True)
    
    # 計算結果
    current_pv = db.Column(db.Integer, default=0)
    previous_pv = db.Column(db.Integer, default=0)
    growth_rate = db.Column(db.Float, default=0)
    
    # ランク
    rank = db.Column(db.Integer, index=True)
    
    # 計算時刻
    calculated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # リレーション
    shop = db.relationship('Shop', backref=db.backref('trending_entry', uselist=False))
    
    __table_args__ = (
        db.UniqueConstraint('shop_id', 'calculated_at', name='uq_trending_shop_time'),
    )
    
    @classmethod
    def get_trending(cls, area=None, limit=10):
        """最新の急上昇店舗を取得"""
        # 最新の計算時刻を取得
        latest = db.session.query(
            db.func.max(cls.calculated_at)
        ).scalar()
        
        if not latest:
            return []
        
        query = cls.query.filter(cls.calculated_at == latest)
        
        if area:
            query = query.filter(cls.area == area)
        
        return query.order_by(cls.rank).limit(limit).all()
    
    @classmethod
    def update_trending(cls, trending_data, area):
        """急上昇データを更新"""
        from .shop import Shop
        
        now = datetime.utcnow()
        
        # 古いデータを削除（24時間以上前）
        cutoff = now - timedelta(hours=24)
        cls.query.filter(cls.calculated_at < cutoff).delete()
        
        # 伸び率でソート
        sorted_data = sorted(
            trending_data.items(),
            key=lambda x: x[1]['growth_rate'],
            reverse=True
        )
        
        # TOP順位を付けて保存
        for rank, (shop_id, data) in enumerate(sorted_data[:50], 1):
            shop = Shop.query.get(shop_id)
            if not shop or shop.area != area:
                continue
            
            entry = cls(
                shop_id=shop_id,
                area=area,
                current_pv=data['current'],
                previous_pv=data['previous'],
                growth_rate=data['growth_rate'],
                rank=rank,
                calculated_at=now
            )
            db.session.add(entry)
        
        db.session.commit()
    
    def __repr__(self):
        return f'<TrendingShop shop={self.shop_id} rank={self.rank}>'


class TrendingCast(db.Model):
    """急上昇キャスト（キャッシュテーブル）"""
    __tablename__ = 'trending_casts'
    
    id = db.Column(db.Integer, primary_key=True)
    cast_id = db.Column(db.Integer, db.ForeignKey('casts.id', ondelete='CASCADE'), nullable=False, index=True)
    area = db.Column(db.String(50), nullable=False, index=True)
    
    # 計算結果
    current_pv = db.Column(db.Integer, default=0)
    previous_pv = db.Column(db.Integer, default=0)
    growth_rate = db.Column(db.Float, default=0)
    
    # ランク
    rank = db.Column(db.Integer, index=True)
    
    # 計算時刻
    calculated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # リレーション
    cast = db.relationship('Cast', backref=db.backref('trending_entry', uselist=False))
    
    __table_args__ = (
        db.UniqueConstraint('cast_id', 'calculated_at', name='uq_trending_cast_time'),
    )
    
    @classmethod
    def get_trending(cls, area=None, limit=10):
        """最新の急上昇キャストを取得"""
        latest = db.session.query(
            db.func.max(cls.calculated_at)
        ).scalar()
        
        if not latest:
            return []
        
        query = cls.query.filter(cls.calculated_at == latest)
        
        if area:
            query = query.filter(cls.area == area)
        
        return query.order_by(cls.rank).limit(limit).all()
    
    def __repr__(self):
        return f'<TrendingCast cast={self.cast_id} rank={self.rank}>'
