#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Application check script"""

import os
import sys

# Move to project root
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

print("=" * 60)
print("Night-Walk System Check")
print("=" * 60)

# 1. App creation test
print("\n[1/5] Creating application...")
try:
    from app import create_app
    app = create_app()
    print("  OK: Application created")
except Exception as e:
    print(f"  ERROR: {e}")
    sys.exit(1)

# 2. Model import test
print("\n[2/5] Importing models...")
try:
    from app.models import (
        User, Shop, AdPlacement, AdEntitlement,
        StorePlan, ShopPageView, TrendingShop, CastShift
    )
    print("  OK: All models imported")
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 3. Service import test
print("\n[3/5] Importing services...")
try:
    from app.services import AdService, TrendingService, RankingService
    print("  OK: All services imported")
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 4. Job import test
print("\n[4/5] Importing jobs...")
try:
    from app.jobs import update_trending, finalize_monthly_rankings
    print("  OK: All jobs imported")
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 5. Database connection test
print("\n[5/5] Checking database...")
try:
    with app.app_context():
        from app.extensions import db
        
        # Check tables
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"  OK: Database connected ({len(tables)} tables)")
        
        # Check new tables
        new_tables = ['ad_placements', 'ad_entitlements', 'store_plans', 
                      'shop_page_views', 'trending_shops', 'cast_shifts']
        missing = [t for t in new_tables if t not in tables]
        if missing:
            print(f"  WARN: Missing tables: {', '.join(missing)}")
        else:
            print(f"  OK: All new tables exist")
        
        # Check data
        placement_count = AdPlacement.query.count()
        plan_count = StorePlan.query.count()
        print(f"  OK: AdPlacement: {placement_count} records")
        print(f"  OK: StorePlan: {plan_count} records")
        
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("ALL CHECKS PASSED!")
print("=" * 60)
