"""
Add commission tables to database
"""
import sys
import os
from datetime import date, datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Shop
from app.models.commission import CommissionRate, Commission, MonthlyBilling

app = create_app('development')

with app.app_context():
    # Create new tables
    db.create_all()
    print("[OK] Commission tables created!")
    
    # Create commission rates for existing shops
    shops = Shop.query.filter_by(is_active=True).all()
    
    for shop in shops:
        if not CommissionRate.query.filter_by(shop_id=shop.id).first():
            rate = CommissionRate(
                shop_id=shop.id,
                commission_type='fixed',
                fixed_amount=1000,
                is_active=True
            )
            db.session.add(rate)
            print(f"[OK] Created commission rate for: {shop.name}")
    
    db.session.commit()
    
    # Create sample commissions for this month
    today = date.today()
    first_shop = Shop.query.first()
    
    if first_shop and Commission.query.count() == 0:
        # Create a few sample commissions
        sample_dates = [
            date(today.year, today.month, max(1, today.day - 5)),
            date(today.year, today.month, max(1, today.day - 3)),
            date(today.year, today.month, max(1, today.day - 1)),
        ]
        
        for i, visit_date in enumerate(sample_dates):
            commission = Commission(
                shop_id=first_shop.id,
                source=Commission.SOURCE_WALK_IN,
                visit_date=visit_date,
                guest_count=i + 1,
                commission_amount=1000 * (i + 1),
                status=Commission.STATUS_CONFIRMED,
                confirmed_at=datetime.utcnow()
            )
            
            # Link to monthly billing
            billing = MonthlyBilling.get_or_create(first_shop.id, visit_date.year, visit_date.month)
            commission.monthly_billing = billing
            
            db.session.add(commission)
        
        db.session.commit()
        
        # Recalculate billing
        billing = MonthlyBilling.query.filter_by(
            shop_id=first_shop.id,
            year=today.year,
            month=today.month
        ).first()
        
        if billing:
            billing.recalculate()
            db.session.commit()
        
        print(f"[OK] Created sample commissions for: {first_shop.name}")
    
    print("\n" + "="*50)
    print("Commission tables setup completed!")
    print("="*50)
