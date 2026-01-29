# app/jobs/ranking_job.py
"""ランキング確定・権利生成ジョブ"""

import logging
from datetime import datetime, date
from calendar import monthrange

logger = logging.getLogger(__name__)


def finalize_monthly_rankings(year=None, month=None, auto_entitlements=True):
    """
    月次ランキングを確定（キャスト＋店舗）
    
    実行頻度: 毎月1日 0:00（前月分を確定）
    
    処理内容:
    1. キャストランキング確定
    2. 店舗ランキング確定（PV＋口コミ）
    3. TOP10にバッジを付与
    4. (オプション) 広告権利を自動生成
    5. 店舗特典（翌月プラン割引）を生成
    
    Args:
        year: 対象年（指定しない場合は前月）
        month: 対象月（指定しない場合は前月）
        auto_entitlements: entitlementを自動生成するか
    """
    from ..extensions import db
    from ..services.ranking_service import RankingService
    from ..services.shop_ranking_service import ShopRankingService
    
    # 年月が指定されない場合は前月
    if year is None or month is None:
        today = date.today()
        if today.month == 1:
            year = today.year - 1
            month = 12
        else:
            year = today.year
            month = today.month - 1
    
    logger.info(f"Starting monthly ranking finalization for {year}/{month}...")
    start_time = datetime.utcnow()
    
    try:
        # キャストランキング確定
        if auto_entitlements:
            cast_result = RankingService.finalize_month_with_entitlements(year, month)
            logger.info(f"[Cast] Created {cast_result['entitlements_created']} entitlements")
        else:
            cast_result = {'rankings': RankingService.finalize_month(year, month)}
        
        # 結果をログ（キャスト）
        for area, rankings in cast_result['rankings'].items():
            if rankings:
                top3 = rankings[:3]
                top_names = [f"#{r['rank']} {r['cast'].name_display}" for r in top3 if r.get('cast')]
                logger.info(f"  [Cast] {area}: {', '.join(top_names)}")
        
        # 店舗ランキング確定
        shop_result = ShopRankingService.finalize_month_with_entitlements(year, month)
        logger.info(f"[Shop] Created {shop_result['entitlements_created']} entitlements")
        logger.info(f"[Shop] Created {len(shop_result['discounts'])} plan discounts")
        
        # 結果をログ（店舗）
        for area, rankings_by_type in shop_result['rankings'].items():
            for rank_type, rankings in rankings_by_type.items():
                if rankings:
                    top3 = rankings[:3]
                    top_names = [f"#{r['rank']} {r['shop'].name}" for r in top3 if r.get('shop')]
                    logger.info(f"  [Shop/{rank_type}] {area}: {', '.join(top_names)}")
        
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"Monthly ranking finalization completed in {elapsed:.2f}s")
        
        return {
            'cast': cast_result,
            'shop': shop_result
        }
        
    except Exception as e:
        logger.error(f"Error in ranking finalization: {e}", exc_info=True)
        db.session.rollback()
        raise


def generate_entitlements(year=None, month=None):
    """
    確定ランキングから広告権利を生成
    
    実行頻度: 毎月1日 0:30（ランキング確定後）
    
    処理内容:
    - TOP1: top_banner, top_badge, platinum (翌月1ヶ月)
    - TOP2-3: top_badge, platinum (翌月1ヶ月)
    - TOP4-10: top_badge (翌月1ヶ月)
    """
    from ..extensions import db
    from ..services.ranking_service import RankingService
    
    # 年月が指定されない場合は前月
    if year is None or month is None:
        today = date.today()
        if today.month == 1:
            year = today.year - 1
            month = 12
        else:
            year = today.year
            month = today.month - 1
    
    logger.info(f"Starting entitlement generation for {year}/{month} rankings...")
    
    try:
        count = RankingService.generate_entitlements_for_rankings(year, month)
        logger.info(f"Generated {count} entitlements")
        return count
        
    except Exception as e:
        logger.error(f"Error in entitlement generation: {e}", exc_info=True)
        db.session.rollback()
        raise


def sync_plan_entitlements():
    """
    有料プランの広告権利を同期
    
    実行頻度: 1日1回
    
    処理内容:
    - 有効な有料プランの権利を確認・更新
    - 期限切れプランの権利を無効化
    """
    from ..extensions import db
    from ..models.store_plan import StorePlan
    
    logger.info("Starting plan entitlement sync...")
    
    try:
        # 有効な有料プランを取得
        active_plans = StorePlan.get_active_paid_plans()
        
        synced = 0
        for plan in active_plans:
            plan.sync_entitlements()
            synced += 1
        
        db.session.commit()
        logger.info(f"Synced entitlements for {synced} plans")
        
    except Exception as e:
        logger.error(f"Error in plan entitlement sync: {e}", exc_info=True)
        db.session.rollback()
        raise


def expire_old_entitlements():
    """
    期限切れの権利を処理
    
    実行頻度: 1日1回
    
    処理内容:
    - 期限切れの権利は自動的にis_valid=Falseになる（DB上は残す）
    - 180日以上前の期限切れ権利を削除（オプション）
    """
    from datetime import timedelta
    from ..extensions import db
    from ..models.ad_entitlement import AdEntitlement
    
    logger.info("Checking expired entitlements...")
    
    now = datetime.utcnow()
    
    # 期限切れ権利の数を確認
    expired_count = AdEntitlement.query.filter(
        AdEntitlement.ends_at < now,
        AdEntitlement.is_active == True
    ).count()
    
    logger.info(f"Found {expired_count} expired but still active entitlements")
    
    # 180日以上前の権利を削除（オプション）
    # old_cutoff = now - timedelta(days=180)
    # deleted = AdEntitlement.query.filter(
    #     AdEntitlement.ends_at < old_cutoff
    # ).delete(synchronize_session=False)
    # db.session.commit()
    # logger.info(f"Deleted {deleted} old entitlements")
