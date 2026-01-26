# app/services/ranking_service.py
"""ランキング計算サービス"""

from datetime import datetime, date
from calendar import monthrange
from sqlalchemy import func
from ..extensions import db
from ..models.gift import Cast, GiftTransaction
from ..models.ranking import (
    CastPageView, CastMonthlyRanking, CastBadgeHistory, RankingConfig,
    AREA_DEFINITIONS
)


class RankingService:
    """ランキング計算・管理サービス"""
    
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
    def get_casts_by_area(cls, area_key):
        """エリアに属するアクティブなキャストを取得"""
        from ..models.shop import Shop
        
        # エリアキーに対応する店舗エリアを取得
        area_def = AREA_DEFINITIONS.get(area_key, {})
        area_name = area_def.get('name', '')
        
        # 岡山エリアの場合、岡山と倉敷の両方を含める
        if area_key == 'okayama':
            area_names = ['岡山', '倉敷']
        else:
            area_names = [area_name]
        
        # 対象店舗のキャストを取得
        return Cast.query.join(Shop).filter(
            Shop.area.in_(area_names),
            Shop.is_active == True,
            Cast.is_active == True
        ).all()
    
    @classmethod
    def calculate_cast_score(cls, cast_id, year, month):
        """キャストのスコアを計算"""
        start, end = cls.get_period_range(year, month)
        
        # ユニークPV数を取得
        pv_count = CastPageView.get_unique_count(cast_id, start, end)
        
        # ギフトポイント・件数を集計
        gift_stats = db.session.query(
            func.sum(GiftTransaction.points_used).label('total_points'),
            func.count(GiftTransaction.id).label('count')
        ).filter(
            GiftTransaction.cast_id == cast_id,
            GiftTransaction.created_at >= start,
            GiftTransaction.created_at <= end,
            GiftTransaction.status == 'completed'
        ).first()
        
        gift_points = gift_stats.total_points or 0
        gift_count = gift_stats.count or 0
        
        # 係数を取得
        pv_weight = RankingConfig.get('pv_weight', 1.0)
        gift_weight = RankingConfig.get('gift_weight', 1.0)
        
        # スコア計算
        pv_score = pv_weight * pv_count
        gift_score = gift_weight * gift_points
        total_score = pv_score + gift_score
        
        return {
            'pv_count': pv_count,
            'gift_points': gift_points,
            'gift_count': gift_count,
            'pv_score': pv_score,
            'gift_score': gift_score,
            'total_score': total_score,
        }
    
    @classmethod
    def calculate_area_ranking(cls, area_key, year, month, finalize=False):
        """エリアのランキングを計算"""
        casts = cls.get_casts_by_area(area_key)
        
        if not casts:
            return []
        
        # 前月のランキングを取得（順位変動表示用）
        prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)
        prev_rankings = {
            r.cast_id: r.rank 
            for r in CastMonthlyRanking.query.filter_by(
                area=area_key, year=prev_year, month=prev_month, is_finalized=True
            ).all()
        }
        
        # 各キャストのスコアを計算
        ranking_data = []
        for cast in casts:
            scores = cls.calculate_cast_score(cast.id, year, month)
            ranking_data.append({
                'cast_id': cast.id,
                'cast': cast,
                'previous_rank': prev_rankings.get(cast.id),
                **scores
            })
        
        # スコア順でソート（同点の場合はギフトポイント優先）
        ranking_data.sort(key=lambda x: (-x['total_score'], -x['gift_points'], -x['pv_count']))
        
        # 順位を付与
        for i, data in enumerate(ranking_data, 1):
            data['rank'] = i
        
        # DBに保存
        for data in ranking_data:
            ranking = CastMonthlyRanking.query.filter_by(
                cast_id=data['cast_id'],
                area=area_key,
                year=year,
                month=month
            ).first()
            
            if not ranking:
                ranking = CastMonthlyRanking(
                    cast_id=data['cast_id'],
                    area=area_key,
                    year=year,
                    month=month
                )
                db.session.add(ranking)
            
            # 上書きされていない場合のみ更新
            if not ranking.is_overridden:
                ranking.pv_count = data['pv_count']
                ranking.gift_points = data['gift_points']
                ranking.gift_count = data['gift_count']
                ranking.pv_score = data['pv_score']
                ranking.gift_score = data['gift_score']
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
        """月次ランキングを確定（全エリア）"""
        results = {}
        
        for area_key in cls.get_active_areas():
            ranking_data = cls.calculate_area_ranking(area_key, year, month, finalize=True)
            results[area_key] = ranking_data
            
            # TOP10にバッジを付与
            for data in ranking_data[:10]:
                ranking = CastMonthlyRanking.query.filter_by(
                    cast_id=data['cast_id'],
                    area=area_key,
                    year=year,
                    month=month
                ).first()
                
                if ranking:
                    # 既存バッジがなければ作成
                    existing = CastBadgeHistory.query.filter_by(
                        cast_id=data['cast_id'],
                        area=area_key,
                        year=year,
                        month=month
                    ).first()
                    
                    if not existing:
                        badge = CastBadgeHistory.create_badge(ranking)
                        if badge:
                            db.session.add(badge)
        
        db.session.commit()
        return results
    
    @classmethod
    def override_ranking(cls, ranking_id, new_rank, reason, user_id):
        """ランキングを強制的に変更（不正対応）"""
        ranking = CastMonthlyRanking.query.get(ranking_id)
        if not ranking:
            return False
        
        old_rank = ranking.rank
        ranking.rank = new_rank
        ranking.is_overridden = True
        ranking.override_reason = reason
        ranking.overridden_by = user_id
        ranking.overridden_at = datetime.utcnow()
        
        # 同エリア・同期間の他のランキングを再調整
        others = CastMonthlyRanking.query.filter(
            CastMonthlyRanking.area == ranking.area,
            CastMonthlyRanking.year == ranking.year,
            CastMonthlyRanking.month == ranking.month,
            CastMonthlyRanking.id != ranking_id,
            CastMonthlyRanking.is_overridden == False
        ).order_by(CastMonthlyRanking.total_score.desc()).all()
        
        # 新しい順位に基づいて再割り当て
        current_rank = 1
        for other in others:
            if current_rank == new_rank:
                current_rank += 1
            other.rank = current_rank
            current_rank += 1
        
        db.session.commit()
        return True
    
    @classmethod
    def disqualify_cast(cls, ranking_id, reason, user_id):
        """キャストを失格（ランキングから除外）"""
        ranking = CastMonthlyRanking.query.get(ranking_id)
        if not ranking:
            return False
        
        ranking.rank = None  # ランキング外
        ranking.is_overridden = True
        ranking.override_reason = f'失格: {reason}'
        ranking.overridden_by = user_id
        ranking.overridden_at = datetime.utcnow()
        
        # バッジを無効化
        badge = CastBadgeHistory.query.filter_by(
            ranking_id=ranking_id
        ).first()
        if badge:
            db.session.delete(badge)
        
        db.session.commit()
        return True
    
    @classmethod
    def get_top1_casts(cls, year=None, month=None):
        """全エリアのTOP1キャストを取得"""
        if year is None or month is None:
            today = date.today()
            # 前月を取得（当月はまだ確定していない可能性があるため）
            if today.month == 1:
                year, month = today.year - 1, 12
            else:
                year, month = today.year, today.month - 1
        
        top1_list = []
        for area_key in cls.get_active_areas():
            ranking = CastMonthlyRanking.get_top1(area_key, year, month)
            if ranking:
                top1_list.append({
                    'area': area_key,
                    'area_name': AREA_DEFINITIONS[area_key]['name'],
                    'ranking': ranking,
                    'cast': ranking.cast
                })
        
        return top1_list
    
    @classmethod
    def record_page_view(cls, cast_id, customer_id=None, session_id=None, 
                         ip_address=None, user_agent=None):
        """キャストのPVを記録"""
        return CastPageView.record_view(
            cast_id=cast_id,
            customer_id=customer_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
