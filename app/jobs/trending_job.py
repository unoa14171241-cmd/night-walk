# app/jobs/trending_job.py
"""急上昇計算ジョブ"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def update_trending():
    """
    急上昇データを更新
    
    実行頻度: 10-15分ごと
    
    処理内容:
    1. 直近60分のPVデータを集計
    2. 伸び率を計算
    3. キャッシュテーブルを更新
    """
    from flask import current_app
    from ..extensions import db
    from ..services.trending_service import TrendingService
    from ..models.shop import Shop
    
    logger.info("Starting trending update job...")
    start_time = datetime.utcnow()
    
    try:
        # 全エリアの急上昇を計算・更新
        for area in Shop.AREAS:
            logger.info(f"Calculating trending for area: {area}")
            TrendingService.update_trending_cache(area=area)
        
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"Trending update completed in {elapsed:.2f}s")
        
    except Exception as e:
        logger.error(f"Error in trending update job: {e}", exc_info=True)
        db.session.rollback()
        raise


def cleanup_old_page_views():
    """
    古いPVデータを削除
    
    実行頻度: 1日1回
    
    処理内容:
    - 90日以上前のPVデータを削除（ストレージ節約）
    """
    from datetime import timedelta
    from ..extensions import db
    from ..models.shop_ranking import ShopPageView
    from ..models.ranking import CastPageView
    
    logger.info("Starting PV cleanup job...")
    
    cutoff = datetime.utcnow() - timedelta(days=90)
    
    try:
        # 店舗PV削除
        shop_deleted = ShopPageView.query.filter(
            ShopPageView.viewed_at < cutoff
        ).delete(synchronize_session=False)
        
        # キャストPV削除
        cast_deleted = CastPageView.query.filter(
            CastPageView.viewed_at < cutoff
        ).delete(synchronize_session=False)
        
        db.session.commit()
        
        logger.info(f"Cleaned up {shop_deleted} shop PVs and {cast_deleted} cast PVs")
        
    except Exception as e:
        logger.error(f"Error in PV cleanup job: {e}", exc_info=True)
        db.session.rollback()
        raise
