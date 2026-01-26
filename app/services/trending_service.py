# app/services/trending_service.py
"""急上昇計算サービス"""

from datetime import datetime, timedelta
from sqlalchemy import func
from ..extensions import db
from ..models.shop import Shop
from ..models.gift import Cast
from ..models.shop_ranking import ShopPageView, TrendingShop, TrendingCast
from ..models.ranking import CastPageView


class TrendingService:
    """
    急上昇計算サービス
    
    直近60分のPV伸び率を計算し、急上昇店舗/キャストをリスト化
    伸び率 = (current - previous) / max(previous, 1)
    """
    
    # 設定
    DEFAULT_WINDOW_MINUTES = 60  # 比較ウィンドウ（分）
    DEFAULT_MIN_PV = 5          # 最小PV閾値（ノイズ除去）
    DEFAULT_LIMIT = 10          # 表示件数
    
    @classmethod
    def calculate_shop_trending(cls, area=None, window_minutes=None, min_pv=None):
        """
        店舗の急上昇を計算
        
        Args:
            area: エリア（null=全エリア）
            window_minutes: 比較ウィンドウ（分）
            min_pv: 最小PV閾値
        
        Returns:
            list: [{'shop': Shop, 'current': int, 'previous': int, 'growth_rate': float, 'rank': int}, ...]
        """
        window = window_minutes or cls.DEFAULT_WINDOW_MINUTES
        min_threshold = min_pv or cls.DEFAULT_MIN_PV
        
        now = datetime.utcnow()
        current_start = now - timedelta(minutes=window)
        previous_start = current_start - timedelta(minutes=window)
        
        # 現在のウィンドウのPV（店舗ごと）
        current_query = db.session.query(
            ShopPageView.shop_id,
            func.count(ShopPageView.id).label('count')
        ).filter(
            ShopPageView.viewed_at >= current_start,
            ShopPageView.viewed_at < now
        ).group_by(ShopPageView.shop_id)
        
        # 直前のウィンドウのPV（店舗ごと）
        previous_query = db.session.query(
            ShopPageView.shop_id,
            func.count(ShopPageView.id).label('count')
        ).filter(
            ShopPageView.viewed_at >= previous_start,
            ShopPageView.viewed_at < current_start
        ).group_by(ShopPageView.shop_id)
        
        current_map = {row.shop_id: row.count for row in current_query.all()}
        previous_map = {row.shop_id: row.count for row in previous_query.all()}
        
        # 全店舗IDを収集
        all_shop_ids = set(current_map.keys()) | set(previous_map.keys())
        
        # 伸び率計算
        trending_data = []
        for shop_id in all_shop_ids:
            current = current_map.get(shop_id, 0)
            previous = previous_map.get(shop_id, 0)
            
            # 最小PV閾値チェック
            if current < min_threshold:
                continue
            
            # 店舗情報取得
            shop = Shop.query.get(shop_id)
            if not shop or not shop.is_active or not shop.is_published:
                continue
            
            # エリアフィルタ
            if area and shop.area != area:
                continue
            
            # 伸び率計算
            growth_rate = (current - previous) / max(previous, 1)
            
            trending_data.append({
                'shop': shop,
                'shop_id': shop_id,
                'current': current,
                'previous': previous,
                'growth_rate': growth_rate,
            })
        
        # 伸び率でソート（高い順）
        trending_data.sort(key=lambda x: -x['growth_rate'])
        
        # ランク付与
        for i, item in enumerate(trending_data, 1):
            item['rank'] = i
        
        return trending_data
    
    @classmethod
    def calculate_cast_trending(cls, area=None, window_minutes=None, min_pv=None):
        """
        キャストの急上昇を計算
        
        Args:
            area: エリア（null=全エリア）
            window_minutes: 比較ウィンドウ（分）
            min_pv: 最小PV閾値
        
        Returns:
            list: [{'cast': Cast, 'current': int, 'previous': int, 'growth_rate': float, 'rank': int}, ...]
        """
        window = window_minutes or cls.DEFAULT_WINDOW_MINUTES
        min_threshold = min_pv or cls.DEFAULT_MIN_PV
        
        now = datetime.utcnow()
        current_start = now - timedelta(minutes=window)
        previous_start = current_start - timedelta(minutes=window)
        
        # 現在のウィンドウのPV（キャストごと）
        current_query = db.session.query(
            CastPageView.cast_id,
            func.count(CastPageView.id).label('count')
        ).filter(
            CastPageView.viewed_at >= current_start,
            CastPageView.viewed_at < now
        ).group_by(CastPageView.cast_id)
        
        # 直前のウィンドウのPV（キャストごと）
        previous_query = db.session.query(
            CastPageView.cast_id,
            func.count(CastPageView.id).label('count')
        ).filter(
            CastPageView.viewed_at >= previous_start,
            CastPageView.viewed_at < current_start
        ).group_by(CastPageView.cast_id)
        
        current_map = {row.cast_id: row.count for row in current_query.all()}
        previous_map = {row.cast_id: row.count for row in previous_query.all()}
        
        # 全キャストIDを収集
        all_cast_ids = set(current_map.keys()) | set(previous_map.keys())
        
        # 伸び率計算
        trending_data = []
        for cast_id in all_cast_ids:
            current = current_map.get(cast_id, 0)
            previous = previous_map.get(cast_id, 0)
            
            # 最小PV閾値チェック
            if current < min_threshold:
                continue
            
            # キャスト情報取得
            cast = Cast.query.get(cast_id)
            if not cast or not cast.is_active:
                continue
            
            # 店舗チェック
            if not cast.shop or not cast.shop.is_active:
                continue
            
            # エリアフィルタ
            if area and cast.shop.area != area:
                continue
            
            # 伸び率計算
            growth_rate = (current - previous) / max(previous, 1)
            
            trending_data.append({
                'cast': cast,
                'cast_id': cast_id,
                'current': current,
                'previous': previous,
                'growth_rate': growth_rate,
            })
        
        # 伸び率でソート
        trending_data.sort(key=lambda x: -x['growth_rate'])
        
        # ランク付与
        for i, item in enumerate(trending_data, 1):
            item['rank'] = i
        
        return trending_data
    
    @classmethod
    def get_trending_shops(cls, area=None, limit=None):
        """
        急上昇店舗を取得（キャッシュから）
        
        Returns:
            list: TrendingShop リスト
        """
        limit = limit or cls.DEFAULT_LIMIT
        return TrendingShop.get_trending(area=area, limit=limit)
    
    @classmethod
    def get_trending_casts(cls, area=None, limit=None):
        """
        急上昇キャストを取得（キャッシュから）
        
        Returns:
            list: TrendingCast リスト
        """
        limit = limit or cls.DEFAULT_LIMIT
        return TrendingCast.get_trending(area=area, limit=limit)
    
    @classmethod
    def update_trending_cache(cls, area=None):
        """
        急上昇キャッシュを更新（定期ジョブから呼び出し）
        """
        now = datetime.utcnow()
        
        # エリアリスト
        if area:
            areas = [area]
        else:
            areas = Shop.AREAS  # ['岡山', '倉敷']
        
        for target_area in areas:
            # 店舗の急上昇を計算
            shop_trending = cls.calculate_shop_trending(area=target_area)
            
            # キャッシュに保存
            for item in shop_trending[:50]:  # TOP50まで保存
                entry = TrendingShop(
                    shop_id=item['shop_id'],
                    area=target_area,
                    current_pv=item['current'],
                    previous_pv=item['previous'],
                    growth_rate=item['growth_rate'],
                    rank=item['rank'],
                    calculated_at=now
                )
                db.session.add(entry)
            
            # キャストの急上昇を計算
            cast_trending = cls.calculate_cast_trending(area=target_area)
            
            # キャッシュに保存
            for item in cast_trending[:50]:
                entry = TrendingCast(
                    cast_id=item['cast_id'],
                    area=target_area,
                    current_pv=item['current'],
                    previous_pv=item['previous'],
                    growth_rate=item['growth_rate'],
                    rank=item['rank'],
                    calculated_at=now
                )
                db.session.add(entry)
        
        # 古いキャッシュを削除（24時間以上前）
        cutoff = now - timedelta(hours=24)
        TrendingShop.query.filter(TrendingShop.calculated_at < cutoff).delete()
        TrendingCast.query.filter(TrendingCast.calculated_at < cutoff).delete()
        
        db.session.commit()
    
    @classmethod
    def record_shop_view(cls, shop_id, customer_id=None, session_id=None,
                         ip_address=None, user_agent=None, referrer=None, page_type='detail'):
        """
        店舗PVを記録
        
        Returns:
            bool: 新規PVが記録されたかどうか
        """
        return ShopPageView.record_view(
            shop_id=shop_id,
            customer_id=customer_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            referrer=referrer,
            page_type=page_type
        )
