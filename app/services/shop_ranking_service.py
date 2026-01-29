# app/services/shop_ranking_service.py
"""店舗ランキング・特典サービス"""

from datetime import datetime, date
from calendar import monthrange
from sqlalchemy import func
from ..extensions import db
from ..models.shop import Shop
from ..models.shop_ranking import ShopPageView, ShopMonthlyRanking
from ..models.review import ShopReviewScore, ShopReview
from ..models.ad_entitlement import AdEntitlement, AdPlacement
from ..models.ranking import AREA_DEFINITIONS


class ShopRankingService:
    """店舗ランキング計算・特典付与サービス"""
    
    # ランキングタイプ
    RANK_TYPE_PV = 'pv'            # PVランキング
    RANK_TYPE_REVIEW = 'review'    # 口コミランキング
    RANK_TYPE_COMBINED = 'combined'  # 総合ランキング
    
    # スコア係数
    PV_WEIGHT = 1.0
    REVIEW_COUNT_WEIGHT = 10.0     # 口コミ数の係数
    REVIEW_RATING_WEIGHT = 100.0   # 平均評価の係数
    
    @staticmethod
    def get_period_range(year, month):
        """月の開始・終了日時を取得"""
        start = datetime(year, month, 1, 0, 0, 0)
        _, last_day = monthrange(year, month)
        end = datetime(year, month, last_day, 23, 59, 59)
        return start, end
    
    @staticmethod
    def get_active_areas():
        """有効なエリア一覧を取得"""
        return {k: v for k, v in AREA_DEFINITIONS.items() if v.get('is_active', False)}
    
    @classmethod
    def get_shops_by_area(cls, area_key):
        """エリアに属するアクティブな店舗を取得"""
        area_def = AREA_DEFINITIONS.get(area_key, {})
        area_name = area_def.get('name', '')
        
        # 岡山エリアの場合、岡山と倉敷の両方を含める
        if area_key == 'okayama':
            area_names = ['岡山', '倉敷']
        else:
            area_names = [area_name]
        
        return Shop.query.filter(
            Shop.area.in_(area_names),
            Shop.is_active == True,
            Shop.is_published == True
        ).all()
    
    @classmethod
    def calculate_shop_score(cls, shop_id, year, month, rank_type='combined'):
        """
        店舗のスコアを計算
        
        Args:
            shop_id: 店舗ID
            year: 年
            month: 月
            rank_type: ランキングタイプ ('pv', 'review', 'combined')
        
        Returns:
            dict: スコア内訳
        """
        start, end = cls.get_period_range(year, month)
        
        # PVスコア計算
        pv_count = ShopPageView.get_count(shop_id, start, end)
        unique_pv = ShopPageView.get_unique_count(shop_id, start, end)
        pv_score = unique_pv * cls.PV_WEIGHT
        
        # 口コミスコア計算
        review_data = ShopReview.get_shop_rating(shop_id)
        review_count = review_data['count']
        average_rating = review_data['average']
        
        # 口コミスコア: 件数 × 平均評価 × 係数
        review_score = (review_count * cls.REVIEW_COUNT_WEIGHT) + \
                       (average_rating * cls.REVIEW_RATING_WEIGHT)
        
        # 総合スコア
        if rank_type == 'pv':
            total_score = pv_score
        elif rank_type == 'review':
            total_score = review_score
        else:  # combined
            total_score = pv_score + review_score
        
        return {
            'pv_count': pv_count,
            'unique_pv_count': unique_pv,
            'pv_score': pv_score,
            'review_count': review_count,
            'average_rating': average_rating,
            'review_score': review_score,
            'total_score': total_score,
        }
    
    @classmethod
    def calculate_area_ranking(cls, area_key, year, month, rank_type='pv', finalize=False):
        """
        エリアのランキングを計算
        
        Args:
            area_key: エリアキー
            year: 年
            month: 月
            rank_type: ランキングタイプ
            finalize: 確定処理を行うか
        
        Returns:
            list: ランキングデータ
        """
        shops = cls.get_shops_by_area(area_key)
        
        if not shops:
            return []
        
        # 前月のランキングを取得（順位変動表示用）
        prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)
        prev_rankings = {
            r.shop_id: r.rank 
            for r in ShopMonthlyRanking.query.filter_by(
                area=area_key, year=prev_year, month=prev_month, 
                rank_type=rank_type, is_finalized=True
            ).all()
        }
        
        # 各店舗のスコアを計算
        ranking_data = []
        for shop in shops:
            scores = cls.calculate_shop_score(shop.id, year, month, rank_type)
            ranking_data.append({
                'shop_id': shop.id,
                'shop': shop,
                'previous_rank': prev_rankings.get(shop.id),
                **scores
            })
        
        # スコア順でソート
        ranking_data.sort(key=lambda x: -x['total_score'])
        
        # 順位を付与
        for i, data in enumerate(ranking_data, 1):
            data['rank'] = i
        
        # DBに保存
        for data in ranking_data:
            ranking = ShopMonthlyRanking.query.filter_by(
                shop_id=data['shop_id'],
                area=area_key,
                rank_type=rank_type,
                year=year,
                month=month
            ).first()
            
            if not ranking:
                ranking = ShopMonthlyRanking(
                    shop_id=data['shop_id'],
                    area=area_key,
                    rank_type=rank_type,
                    year=year,
                    month=month
                )
                db.session.add(ranking)
            
            # 上書きされていない場合のみ更新
            if not ranking.is_overridden:
                ranking.pv_count = data['pv_count']
                ranking.unique_pv_count = data['unique_pv_count']
                ranking.total_score = data['total_score']
                ranking.rank = data['rank']
                ranking.previous_rank = data['previous_rank']
            
            if finalize and not ranking.is_finalized:
                ranking.is_finalized = True
                ranking.finalized_at = datetime.utcnow()
        
        db.session.commit()
        
        return ranking_data
    
    @classmethod
    def finalize_month(cls, year, month):
        """
        月次ランキングを確定（全エリア・全タイプ）
        
        Returns:
            dict: 各エリア・タイプのランキング結果
        """
        results = {}
        
        for area_key in cls.get_active_areas():
            results[area_key] = {}
            
            # PVランキング
            results[area_key]['pv'] = cls.calculate_area_ranking(
                area_key, year, month, rank_type='pv', finalize=True
            )
            
            # 口コミランキング（※口コミがある場合のみ）
            results[area_key]['review'] = cls.calculate_area_ranking(
                area_key, year, month, rank_type='review', finalize=True
            )
        
        return results
    
    @classmethod
    def generate_shop_entitlements(cls, year, month, user_id=None):
        """
        確定ランキングから店舗特典を自動生成
        
        特典内容:
        - 1位: トップバナー無料掲載 + TOPバッジ + 翌月プラン無料
        - 2位: TOPバッジ + 翌月プラン50%OFF
        - 3位: TOPバッジ + 翌月プラン30%OFF
        
        Returns:
            int: 生成された特典数
        """
        # 有効期間を計算（翌月1日〜月末）
        if month == 12:
            valid_year = year + 1
            valid_month = 1
        else:
            valid_year = year
            valid_month = month + 1
        
        starts_at = datetime(valid_year, valid_month, 1, 0, 0, 0)
        _, last_day = monthrange(valid_year, valid_month)
        ends_at = datetime(valid_year, valid_month, last_day, 23, 59, 59)
        
        created_count = 0
        
        for area_key in cls.get_active_areas():
            # PVランキングのTOP3
            pv_rankings = ShopMonthlyRanking.get_ranking(
                area_key, year, month, rank_type='pv', limit=3
            )
            
            for ranking in pv_rankings:
                if not ranking.rank:
                    continue
                
                rank = ranking.rank
                
                # 1位: バナー + バッジ + 無料
                if rank == 1:
                    cls._create_shop_entitlement(
                        ranking=ranking,
                        placement_type=AdPlacement.TYPE_TOP_BANNER,
                        starts_at=starts_at,
                        ends_at=ends_at,
                        metadata={
                            'rank': rank, 
                            'year': year, 
                            'month': month, 
                            'rank_type': 'pv',
                            'banner_eligible': True
                        },
                        user_id=user_id
                    )
                    created_count += 1
                
                # 1-3位: バッジ
                if rank <= 3:
                    cls._create_shop_entitlement(
                        ranking=ranking,
                        placement_type=AdPlacement.TYPE_TOP_BADGE,
                        starts_at=starts_at,
                        ends_at=ends_at,
                        metadata={
                            'rank': rank,
                            'year': year,
                            'month': month,
                            'rank_type': 'pv',
                            'badge_type': f'top{rank}'
                        },
                        user_id=user_id
                    )
                    created_count += 1
            
            # 口コミランキングのTOP3も同様に処理
            review_rankings = ShopMonthlyRanking.get_ranking(
                area_key, year, month, rank_type='review', limit=3
            )
            
            for ranking in review_rankings:
                if not ranking.rank or ranking.rank > 3:
                    continue
                
                rank = ranking.rank
                
                # 口コミ1位: バナー
                if rank == 1:
                    cls._create_shop_entitlement(
                        ranking=ranking,
                        placement_type=AdPlacement.TYPE_TOP_BANNER,
                        starts_at=starts_at,
                        ends_at=ends_at,
                        metadata={
                            'rank': rank,
                            'year': year,
                            'month': month,
                            'rank_type': 'review',
                            'banner_eligible': True
                        },
                        user_id=user_id
                    )
                    created_count += 1
                
                # 口コミTOP3: バッジ
                cls._create_shop_entitlement(
                    ranking=ranking,
                    placement_type=AdPlacement.TYPE_TOP_BADGE,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    metadata={
                        'rank': rank,
                        'year': year,
                        'month': month,
                        'rank_type': 'review',
                        'badge_type': f'review_top{rank}'
                    },
                    user_id=user_id
                )
                created_count += 1
        
        db.session.commit()
        return created_count
    
    @classmethod
    def _create_shop_entitlement(cls, ranking, placement_type, starts_at, ends_at, metadata=None, user_id=None):
        """店舗の広告権利を作成"""
        # 既存チェック
        existing = AdEntitlement.query.filter_by(
            target_type=AdEntitlement.TARGET_SHOP,
            target_id=ranking.shop_id,
            placement_type=placement_type,
            source_type=AdEntitlement.SOURCE_RANKING,
            source_id=ranking.id
        ).first()
        
        if existing:
            return existing
        
        # 優先度決定（ランク順）
        priority = 100 - (ranking.rank or 100)
        
        entitlement = AdEntitlement(
            target_type=AdEntitlement.TARGET_SHOP,
            target_id=ranking.shop_id,
            placement_type=placement_type,
            area=ranking.area,
            priority=priority,
            starts_at=starts_at,
            ends_at=ends_at,
            source_type=AdEntitlement.SOURCE_RANKING,
            source_id=ranking.id,
            extra_data=metadata or {},
            is_active=True,
            created_by=user_id
        )
        
        db.session.add(entitlement)
        return entitlement
    
    @classmethod
    def generate_plan_discounts(cls, year, month):
        """
        確定ランキングから翌月のプラン割引を生成
        
        割引内容:
        - 1位: 翌月プラン100%OFF（無料）
        - 2位: 翌月プラン50%OFF
        - 3位: 翌月プラン30%OFF
        
        Returns:
            list: 生成された割引情報
        """
        from ..models.store_plan import StorePlan
        
        # 有効期間を計算（翌月）
        if month == 12:
            valid_year = year + 1
            valid_month = 1
        else:
            valid_year = year
            valid_month = month + 1
        
        discounts = []
        discount_rates = {1: 100, 2: 50, 3: 30}  # 順位: 割引率
        
        for area_key in cls.get_active_areas():
            # PVランキングと口コミランキングのTOP3
            for rank_type in ['pv', 'review']:
                rankings = ShopMonthlyRanking.get_ranking(
                    area_key, year, month, rank_type=rank_type, limit=3
                )
                
                for ranking in rankings:
                    if not ranking.rank or ranking.rank > 3:
                        continue
                    
                    discount_rate = discount_rates.get(ranking.rank, 0)
                    if discount_rate == 0:
                        continue
                    
                    # 割引情報を記録
                    discount_info = {
                        'shop_id': ranking.shop_id,
                        'area': area_key,
                        'rank': ranking.rank,
                        'rank_type': rank_type,
                        'discount_rate': discount_rate,
                        'valid_year': valid_year,
                        'valid_month': valid_month,
                        'source_ranking_id': ranking.id
                    }
                    discounts.append(discount_info)
                    
                    # 店舗プランに割引を適用（StorePlanのdiscount_rateフィールドがあれば）
                    plan = StorePlan.query.filter_by(shop_id=ranking.shop_id, is_active=True).first()
                    if plan:
                        # extra_dataに割引情報を保存
                        if not plan.extra_data:
                            plan.extra_data = {}
                        
                        plan.extra_data[f'ranking_discount_{valid_year}_{valid_month}'] = {
                            'discount_rate': discount_rate,
                            'rank': ranking.rank,
                            'rank_type': rank_type,
                            'area': area_key
                        }
        
        db.session.commit()
        return discounts
    
    @classmethod
    def finalize_month_with_entitlements(cls, year, month, user_id=None):
        """
        月次ランキングを確定し、特典も自動生成
        
        Returns:
            dict: {'rankings': dict, 'entitlements_created': int, 'discounts': list}
        """
        # ランキング確定
        rankings = cls.finalize_month(year, month)
        
        # entitlement自動生成
        entitlements_count = cls.generate_shop_entitlements(year, month, user_id)
        
        # プラン割引生成
        discounts = cls.generate_plan_discounts(year, month)
        
        return {
            'rankings': rankings,
            'entitlements_created': entitlements_count,
            'discounts': discounts
        }
    
    @classmethod
    def get_shop_active_discounts(cls, shop_id):
        """
        店舗の現在有効な割引を取得
        
        Returns:
            list: 有効な割引情報
        """
        from ..models.store_plan import StorePlan
        
        today = date.today()
        current_year = today.year
        current_month = today.month
        
        plan = StorePlan.query.filter_by(shop_id=shop_id, is_active=True).first()
        if not plan or not plan.extra_data:
            return []
        
        discount_key = f'ranking_discount_{current_year}_{current_month}'
        discount = plan.extra_data.get(discount_key)
        
        if discount:
            return [discount]
        
        return []
    
    @classmethod
    def record_page_view(cls, shop_id, customer_id=None, session_id=None,
                         ip_address=None, user_agent=None, referrer=None, page_type='detail'):
        """店舗のPVを記録"""
        return ShopPageView.record_view(
            shop_id=shop_id,
            customer_id=customer_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            referrer=referrer,
            page_type=page_type
        )
    
    @classmethod
    def get_top_shops(cls, area_key=None, year=None, month=None, rank_type='pv', limit=10):
        """
        TOP店舗を取得
        
        Args:
            area_key: エリアキー（None=全エリア）
            year: 年（None=前月）
            month: 月（None=前月）
            rank_type: ランキングタイプ
            limit: 取得数
        
        Returns:
            list: ランキング情報
        """
        if year is None or month is None:
            today = date.today()
            if today.month == 1:
                year, month = today.year - 1, 12
            else:
                year, month = today.year, today.month - 1
        
        query = ShopMonthlyRanking.query.filter(
            ShopMonthlyRanking.year == year,
            ShopMonthlyRanking.month == month,
            ShopMonthlyRanking.rank_type == rank_type,
            ShopMonthlyRanking.is_finalized == True,
            ShopMonthlyRanking.rank != None
        )
        
        if area_key:
            query = query.filter(ShopMonthlyRanking.area == area_key)
        
        return query.order_by(ShopMonthlyRanking.rank).limit(limit).all()
