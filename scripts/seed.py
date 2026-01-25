"""
Night-Walk MVP - Seed Script
Creates initial data for development/testing
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.user import User, ShopMember
from app.models.shop import Shop, VacancyStatus
from app.models.job import Job
from app.models.billing import Subscription


def seed():
    """Create initial seed data."""
    app = create_app()
    
    with app.app_context():
        # Check if data already exists
        if User.query.first():
            print("Database already contains data. Skipping seed.")
            return
        
        print("Creating seed data...")
        
        # Create admin user
        admin = User(
            email='admin@night-walk.jp',
            name='管理者',
            role='admin',
        )
        admin.set_password('admin123')
        db.session.add(admin)
        print("[OK] Created admin user (admin@night-walk.jp / admin123)")
        
        # Create sample shops
        shops_data = [
            {
                'name': 'Club ROYAL',
                'area': '岡山',
                'phone': '086-XXX-0001',
                'business_hours': '20:00〜02:00',
                'price_range': '5,000円〜',
                'description': '岡山駅前の人気クラブ。広々とした店内でゆったりとお過ごしいただけます。',
                'is_published': True,
            },
            {
                'name': 'Lounge MOON',
                'area': '岡山',
                'phone': '086-XXX-0002',
                'business_hours': '19:00〜01:00',
                'price_range': '4,000円〜',
                'description': '落ち着いた雰囲気のラウンジ。お酒と会話をお楽しみください。',
                'is_published': True,
            },
            {
                'name': 'Bar STELLA',
                'area': '倉敷',
                'phone': '086-XXX-0003',
                'business_hours': '21:00〜03:00',
                'price_range': '3,000円〜',
                'description': '倉敷美観地区近くの隠れ家バー。こだわりのカクテルをご用意。',
                'is_published': True,
            },
        ]
        
        for shop_data in shops_data:
            shop = Shop(**shop_data)
            db.session.add(shop)
            db.session.flush()
            
            # Create vacancy status
            vacancy = VacancyStatus(shop_id=shop.id, status='unknown')
            db.session.add(vacancy)
            
            # Create subscription (trial)
            subscription = Subscription(shop_id=shop.id, status='trial')
            db.session.add(subscription)
            
            print(f"[OK] Created shop: {shop.name}")
        
        # Create shop owner user
        owner = User(
            email='owner@example.com',
            name='店舗オーナー',
            role='owner',
        )
        owner.set_password('owner123')
        db.session.add(owner)
        db.session.flush()
        
        # Link owner to first shop
        first_shop = Shop.query.first()
        membership = ShopMember(shop_id=first_shop.id, user_id=owner.id, role='owner')
        db.session.add(membership)
        print(f"[OK] Created owner user (owner@example.com / owner123) for {first_shop.name}")
        
        # Create staff user
        staff = User(
            email='staff@example.com',
            name='スタッフ',
            role='staff',
        )
        staff.set_password('staff123')
        db.session.add(staff)
        db.session.flush()
        
        # Link staff to first shop
        membership2 = ShopMember(shop_id=first_shop.id, user_id=staff.id, role='staff')
        db.session.add(membership2)
        print(f"[OK] Created staff user (staff@example.com / staff123) for {first_shop.name}")
        
        # Create sample job for first shop
        job = Job(
            shop_id=first_shop.id,
            is_active=True,
            hourly_wage='3,000円〜5,000円',
            benefits='日払い可、送迎あり、制服貸与',
            trial_available=True,
        )
        db.session.add(job)
        print(f"[OK] Created job posting for {first_shop.name}")
        
        db.session.commit()
        print("\n[SUCCESS] Seed completed successfully!")
        print("\nLogin credentials:")
        print("  Admin:  admin@night-walk.jp / admin123")
        print("  Owner:  owner@example.com / owner123")
        print("  Staff:  staff@example.com / staff123")


if __name__ == '__main__':
    seed()
