#!/usr/bin/env python
"""
広告・露出制御システムのテーブル追加マイグレーション

実行方法:
    python scripts/add_ad_system.py

追加されるテーブル:
    - ad_placements (広告枠定義)
    - ad_entitlements (広告権利)
    - store_plans (店舗有料プラン)
    - store_plan_history (プラン変更履歴)
    - shop_page_views (店舗PV記録)
    - shop_monthly_rankings (店舗月次ランキング)
    - trending_shops (急上昇店舗)
    - trending_casts (急上昇キャスト)
    - cast_shifts (キャスト出勤シフト)
    - shift_templates (シフトテンプレート)
"""

import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import (
    AdPlacement, AdEntitlement,
    StorePlan, StorePlanHistory,
    ShopPageView, ShopMonthlyRanking, TrendingShop, TrendingCast,
    CastShift, ShiftTemplate
)


def create_tables():
    """新しいテーブルを作成"""
    print("Creating new tables...")
    
    # 各モデルのテーブルを作成
    tables = [
        AdPlacement.__table__,
        AdEntitlement.__table__,
        StorePlan.__table__,
        StorePlanHistory.__table__,
        ShopPageView.__table__,
        ShopMonthlyRanking.__table__,
        TrendingShop.__table__,
        TrendingCast.__table__,
        CastShift.__table__,
        ShiftTemplate.__table__,
    ]
    
    for table in tables:
        try:
            table.create(db.engine, checkfirst=True)
            print(f"  ✓ Created table: {table.name}")
        except Exception as e:
            print(f"  ✗ Error creating {table.name}: {e}")
    
    print("Tables created successfully!")


def init_ad_placements():
    """広告枠のデフォルト定義を初期化"""
    print("\nInitializing ad placements...")
    
    AdPlacement.ensure_defaults()
    
    # 確認
    placements = AdPlacement.get_all_active()
    for p in placements:
        print(f"  ✓ {p.placement_type}: {p.name}")
    
    print(f"Initialized {len(placements)} ad placements")


def create_sample_store_plans():
    """既存店舗に無料プランを設定（サンプルデータ）"""
    from app.models import Shop
    
    print("\nCreating free plans for existing shops...")
    
    shops = Shop.query.filter_by(is_active=True).all()
    count = 0
    
    for shop in shops:
        existing = StorePlan.query.filter_by(shop_id=shop.id).first()
        if not existing:
            plan = StorePlan.get_or_create_free(shop.id)
            count += 1
            print(f"  ✓ Created free plan for: {shop.name}")
    
    db.session.commit()
    print(f"Created {count} free plans")


def main():
    """メイン実行"""
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("Night-Walk 広告・露出制御システム マイグレーション")
        print("=" * 60)
        
        # テーブル作成
        create_tables()
        
        # デフォルトデータ初期化
        init_ad_placements()
        
        # サンプルデータ作成
        create_sample_store_plans()
        
        db.session.commit()
        
        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)


if __name__ == '__main__':
    main()
