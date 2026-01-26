#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Quick migration runner - run from project root
"""
import os
import sys

# Ensure we're in the right directory
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

from app import create_app
from app.extensions import db
from app.models import (
    AdPlacement, AdEntitlement,
    StorePlan, StorePlanHistory,
    ShopPageView, ShopMonthlyRanking, TrendingShop, TrendingCast,
    CastShift, ShiftTemplate
)


def main():
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("Night-Walk Ad System Migration")
        print("=" * 60)
        
        # Create tables
        print("\nCreating new tables...")
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
                print(f"  OK: {table.name}")
            except Exception as e:
                print(f"  Error {table.name}: {e}")
        
        # Initialize default ad placements
        print("\nInitializing ad placements...")
        AdPlacement.ensure_defaults()
        
        placements = AdPlacement.get_all_active()
        for p in placements:
            print(f"  OK: {p.placement_type}")
        
        # Create free plans for existing shops
        print("\nCreating free plans for existing shops...")
        from app.models import Shop
        
        shops = Shop.query.filter_by(is_active=True).all()
        count = 0
        
        for shop in shops:
            existing = StorePlan.query.filter_by(shop_id=shop.id).first()
            if not existing:
                plan = StorePlan.get_or_create_free(shop.id)
                count += 1
                print(f"  OK: {shop.name}")
        
        db.session.commit()
        
        print("\n" + "=" * 60)
        print(f"Migration completed! Created plans for {count} shops.")
        print("=" * 60)


if __name__ == '__main__':
    main()
