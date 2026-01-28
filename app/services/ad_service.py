# app/services/ad_service.py
"""広告表示決定サービス"""

from datetime import datetime, date
from sqlalchemy import or_
from ..extensions import db
from ..models.ad_entitlement import AdPlacement, AdEntitlement
from ..models.store_plan import StorePlan
from ..models.shop import Shop
from ..models.gift import Cast


class AdService:
    """
    広告表示決定サービス
    
    優先度:
    P0: ランキング特典 (top_badge, platinum, top_banner)
    P1: 有料プラン (search_boost, premium_badge, job_board, cast_display)
    P2: 通常表示
    """
    
    @classmethod
    def get_search_results(cls, area=None, keyword=None, scene=None, category=None, 
                          price_range_key=None, vacancy_status=None, 
                          has_job=None, featured_only=False):
        """
        検索結果を広告優先度順で返す
        
        優先度:
        1. ランキング特典によるSEARCH_BOOST（priority高）
        2. 有料プランによるSEARCH_BOOST（premium > standard）
        3. is_featured（おすすめ）
        4. 通常（created_at降順）
        """
        # 通常の検索結果を取得
        shops = Shop.search(
            keyword=keyword,
            area=area,
            scene=scene,
            category=category,
            price_range_key=price_range_key,
            vacancy_status=vacancy_status,
            has_job=has_job,
            featured_only=featured_only
        )
        
        if not shops:
            return []
        
        # 検索優先表示の権利を取得
        boost_map = AdEntitlement.get_search_boost_shop_ids(area=area)
        
        # 有料プランの店舗を取得
        paid_plan_shops = cls.get_paid_plan_shop_ids()
        
        def sort_key(shop):
            # entitlementによるブースト優先度
            entitlement_priority = boost_map.get(shop.id, 0)
            
            # 有料プラン優先度（プレミアム=20, スタンダード=10, 無料=0）
            plan_priority = paid_plan_shops.get(shop.id, 0)
            
            # おすすめフラグ
            featured = 1 if shop.is_featured else 0
            
            # 総合優先度（負の値でソート）
            return (-entitlement_priority, -plan_priority, -featured, -shop.id)
        
        return sorted(shops, key=sort_key)
    
    @classmethod
    def get_paid_plan_shop_ids(cls):
        """有料プランの店舗IDと優先度を取得"""
        plans = StorePlan.query.filter(
            StorePlan.plan_type.in_([StorePlan.PLAN_STANDARD, StorePlan.PLAN_PREMIUM]),
            StorePlan.status.in_([StorePlan.STATUS_ACTIVE, StorePlan.STATUS_TRIAL])
        ).all()
        
        priority_map = {
            StorePlan.PLAN_PREMIUM: 20,
            StorePlan.PLAN_STANDARD: 10,
        }
        
        return {p.shop_id: priority_map.get(p.plan_type, 0) for p in plans}
    
    @classmethod
    def get_top_banner(cls, area):
        """
        エリアトップバナーを取得
        
        Returns:
            list: [{'target': Shop/Cast, 'target_type': str, 'entitlement': AdEntitlement, 'image_url': str}, ...]
        """
        entitlements = AdEntitlement.get_active(
            placement_type=AdPlacement.TYPE_TOP_BANNER,
            area=area
        )
        
        results = []
        for ent in entitlements:
            target = ent.target
            if not target:
                continue
            
            # 画像URLの決定
            if ent.target_type == AdEntitlement.TARGET_SHOP:
                image_url = target.main_image_url
            else:
                image_url = target.image_url if hasattr(target, 'image_url') else None
            
            # メタデータから画像URLを上書き（指定がある場合）
            extra = ent.extra_data or {}
            if extra.get('banner_image_url'):
                image_url = extra.get('banner_image_url')
            
            results.append({
                'target': target,
                'target_type': ent.target_type,
                'entitlement': ent,
                'image_url': image_url,
                'link_url': extra.get('link_url'),
                'priority': ent.priority,
            })
        
        return sorted(results, key=lambda x: -x['priority'])
    
    @classmethod
    def get_shop_badges(cls, shop_id):
        """
        店舗のバッジを取得
        
        Returns:
            dict: {'premium_badge': bool, 'top_badges': list, 'has_job_board': bool, 'has_cast_display': bool}
        """
        entitlements = AdEntitlement.get_for_target(
            target_type=AdEntitlement.TARGET_SHOP,
            target_id=shop_id,
            active_only=True
        )
        
        result = {
            'premium_badge': False,
            'top_badges': [],
            'has_job_board': False,
            'has_cast_display': False,
        }
        
        for ent in entitlements:
            if ent.placement_type == AdPlacement.TYPE_PREMIUM_BADGE:
                result['premium_badge'] = True
            elif ent.placement_type == AdPlacement.TYPE_TOP_BADGE:
                extra = ent.extra_data or {}
                result['top_badges'].append({
                    'rank': extra.get('rank'),
                    'area': ent.area,
                })
            elif ent.placement_type == AdPlacement.TYPE_JOB_BOARD:
                result['has_job_board'] = True
            elif ent.placement_type == AdPlacement.TYPE_CAST_DISPLAY:
                result['has_cast_display'] = True
        
        return result
    
    @classmethod
    def get_cast_badges(cls, cast_id):
        """
        キャストのバッジを取得
        
        Returns:
            dict: {'top_badges': list, 'has_platinum': bool, 'platinum_level': int}
        """
        entitlements = AdEntitlement.get_for_target(
            target_type=AdEntitlement.TARGET_CAST,
            target_id=cast_id,
            active_only=True
        )
        
        result = {
            'top_badges': [],
            'has_platinum': False,
            'platinum_level': 0,
        }
        
        for ent in entitlements:
            if ent.placement_type == AdPlacement.TYPE_TOP_BADGE:
                extra = ent.extra_data or {}
                result['top_badges'].append({
                    'rank': extra.get('rank'),
                    'area': ent.area,
                    'year': extra.get('year'),
                    'month': extra.get('month'),
                })
            elif ent.placement_type == AdPlacement.TYPE_PLATINUM_PROFILE:
                result['has_platinum'] = True
                extra = ent.extra_data or {}
                result['platinum_level'] = max(result['platinum_level'], extra.get('level', 1))
        
        # バッジをランク順でソート
        result['top_badges'].sort(key=lambda x: x.get('rank', 999))
        
        return result
    
    @classmethod
    def get_best_badge(cls, target_type, target_id):
        """
        最も良いバッジを取得
        
        Returns:
            dict or None: {'type': 'top1'/'top3'/'top10'/'premium', 'rank': int, 'label': str, 'color': str}
        """
        if target_type == 'shop':
            badges = cls.get_shop_badges(target_id)
            if badges['top_badges']:
                best = badges['top_badges'][0]
                rank = best.get('rank', 10)
                if rank == 1:
                    return {'type': 'top1', 'rank': 1, 'label': 'TOP1', 'color': 'gold'}
                elif rank <= 3:
                    return {'type': 'top3', 'rank': rank, 'label': f'TOP{rank}', 'color': 'silver'}
                else:
                    return {'type': 'top10', 'rank': rank, 'label': f'TOP{rank}', 'color': 'bronze'}
            if badges['premium_badge']:
                return {'type': 'premium', 'rank': None, 'label': '優良店', 'color': 'premium'}
        else:
            badges = cls.get_cast_badges(target_id)
            if badges['top_badges']:
                best = badges['top_badges'][0]
                rank = best.get('rank', 10)
                if rank == 1:
                    return {'type': 'top1', 'rank': 1, 'label': 'TOP1', 'color': 'gold'}
                elif rank <= 3:
                    return {'type': 'top3', 'rank': rank, 'label': f'TOP{rank}', 'color': 'silver'}
                else:
                    return {'type': 'top10', 'rank': rank, 'label': f'TOP{rank}', 'color': 'bronze'}
            if badges['has_platinum']:
                return {'type': 'platinum', 'rank': None, 'label': 'プラチナ', 'color': 'platinum'}
        
        return None
    
    @classmethod
    def can_show_job(cls, shop_id):
        """求人表示可能か確認"""
        # 有料プランまたは求人掲載権限があるか
        return AdEntitlement.has_entitlement(
            target_type=AdEntitlement.TARGET_SHOP,
            target_id=shop_id,
            placement_type=AdPlacement.TYPE_JOB_BOARD
        )
    
    @classmethod
    def can_show_cast_shift(cls, shop_id):
        """キャスト出勤表示可能か確認"""
        return AdEntitlement.has_entitlement(
            target_type=AdEntitlement.TARGET_SHOP,
            target_id=shop_id,
            placement_type=AdPlacement.TYPE_CAST_DISPLAY
        )
    
    @classmethod
    def get_inline_ads(cls, area=None, limit=5):
        """
        一覧内広告を取得
        
        Returns:
            list: 店舗一覧内に挿入する広告リスト
        """
        entitlements = AdEntitlement.get_active(
            placement_type=AdPlacement.TYPE_INLINE_AD,
            area=area
        )
        
        results = []
        for ent in entitlements[:limit]:
            target = ent.target
            if not target:
                continue
            
            extra = ent.extra_data or {}
            results.append({
                'target': target,
                'target_type': ent.target_type,
                'entitlement': ent,
                'display_as_ad': True,
            })
        
        return results
    
    @classmethod
    def enrich_shop_list(cls, shops):
        """
        店舗リストにバッジ情報を付加
        
        Args:
            shops: Shop リスト
        
        Returns:
            list: バッジ情報が付加されたdict リスト
        """
        if not shops:
            return []
        
        shop_ids = [s.id for s in shops]
        
        # 一括でバッジ情報を取得
        entitlements = AdEntitlement.query.filter(
            AdEntitlement.target_type == AdEntitlement.TARGET_SHOP,
            AdEntitlement.target_id.in_(shop_ids),
            AdEntitlement.is_active == True,
            AdEntitlement.starts_at <= datetime.utcnow(),
            AdEntitlement.ends_at >= datetime.utcnow()
        ).all()
        
        # 店舗ごとにグループ化
        badge_map = {}
        for ent in entitlements:
            if ent.target_id not in badge_map:
                badge_map[ent.target_id] = []
            badge_map[ent.target_id].append(ent)
        
        results = []
        for shop in shops:
            shop_ents = badge_map.get(shop.id, [])
            badge = cls._determine_best_badge(shop_ents)
            
            results.append({
                'shop': shop,
                'badge': badge,
                'is_premium': any(e.placement_type == AdPlacement.TYPE_PREMIUM_BADGE for e in shop_ents),
                'has_boost': any(e.placement_type == AdPlacement.TYPE_SEARCH_BOOST for e in shop_ents),
            })
        
        return results
    
    @classmethod
    def _determine_best_badge(cls, entitlements):
        """entitlement リストから最良のバッジを決定"""
        top_badge = None
        premium_badge = False
        
        for ent in entitlements:
            if ent.placement_type == AdPlacement.TYPE_TOP_BADGE:
                extra = ent.extra_data or {}
                rank = extra.get('rank', 999)
                if top_badge is None or rank < top_badge.get('rank', 999):
                    top_badge = {'rank': rank, 'area': ent.area}
            elif ent.placement_type == AdPlacement.TYPE_PREMIUM_BADGE:
                premium_badge = True
        
        if top_badge:
            rank = top_badge['rank']
            if rank == 1:
                return {'type': 'top1', 'rank': 1, 'label': 'TOP1', 'color': 'gold'}
            elif rank <= 3:
                return {'type': 'top3', 'rank': rank, 'label': f'TOP{rank}', 'color': 'silver'}
            else:
                return {'type': 'top10', 'rank': rank, 'label': f'TOP{rank}', 'color': 'bronze'}
        
        if premium_badge:
            return {'type': 'premium', 'rank': None, 'label': '優良店', 'color': 'premium'}
        
        return None
