"""
Recreate database with all new models
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import *
from app.models.shop import VacancyStatus
from app.models.billing import Subscription

app = create_app('development')

with app.app_context():
    # Drop all tables and recreate
    print("Dropping all tables...")
    db.drop_all()
    
    print("Creating all tables...")
    db.create_all()
    
    # Create admin user
    admin_user = User(email='admin@night-walk.jp', name='Admin User', role='admin')
    admin_user.set_password('admin123')
    db.session.add(admin_user)
    db.session.commit()
    print("[OK] Created admin user (admin@night-walk.jp / admin123)")
    
    # Create owner user
    owner_user = User(email='owner@example.com', name='Tanaka Owner', role='owner')
    owner_user.set_password('owner123')
    db.session.add(owner_user)
    db.session.commit()
    print("[OK] Created owner user (owner@example.com / owner123)")
    
    # Create staff user
    staff_user = User(email='staff@example.com', name='Suzuki Staff', role='staff')
    staff_user.set_password('staff123')
    db.session.add(staff_user)
    db.session.commit()
    print("[OK] Created staff user (staff@example.com / staff123)")
    
    # Create sample shops
    shops_data = [
        {
            'name': 'Lounge MIYABI',
            'area': Shop.AREA_OKAYAMA,
            'phone': '086-123-4567',
            'address': '岡山市北区本町1-2-3',
            'business_hours': '20:00~02:00',
            'price_range': '5,000円~10,000円',
            'price_min': 5000,
            'price_max': 10000,
            'description': '落ち着いた雰囲気の中、上質な時間をお過ごしいただけます。',
            'category': 'lounge',
            'tags': '駅近,個室あり,VIP対応',
            'is_published': True,
            'is_featured': True,
        },
        {
            'name': 'Club LUXE',
            'area': Shop.AREA_OKAYAMA,
            'phone': '086-234-5678',
            'address': '岡山市北区駅前町2-3-4',
            'business_hours': '21:00~05:00',
            'price_range': '8,000円~15,000円',
            'price_min': 8000,
            'price_max': 15000,
            'description': '最新の音響設備と華やかな内装で、特別な夜をお楽しみください。',
            'category': 'club',
            'tags': 'カラオケあり,シャンパン',
            'is_published': True,
            'is_featured': False,
        },
        {
            'name': 'Bar KURA',
            'area': Shop.AREA_KURASHIKI,
            'phone': '086-345-6789',
            'address': '倉敷市阿知1-2-3',
            'business_hours': '18:00~01:00',
            'price_range': '3,000円~8,000円',
            'price_min': 3000,
            'price_max': 8000,
            'description': '厳選されたウイスキーと共に、大人の時間を。',
            'category': 'bar',
            'tags': 'ウイスキー,静かな空間,一人歓迎',
            'is_published': True,
            'is_featured': False,
        },
    ]
    
    for shop_data in shops_data:
        shop = Shop(**shop_data)
        db.session.add(shop)
        db.session.flush()
        
        # Create vacancy status
        vacancy = VacancyStatus(shop_id=shop.id, status='empty')
        db.session.add(vacancy)
        
        # Create subscription
        subscription = Subscription(shop_id=shop.id, status='trial')
        db.session.add(subscription)
        
        print(f"[OK] Created shop: {shop.name}")
    
    db.session.commit()
    
    # Get the first shop for member assignment
    first_shop = Shop.query.first()
    
    # Create shop members
    owner_member = ShopMember(shop_id=first_shop.id, user_id=owner_user.id, role='owner')
    staff_member = ShopMember(shop_id=first_shop.id, user_id=staff_user.id, role='staff')
    db.session.add(owner_member)
    db.session.add(staff_member)
    db.session.commit()
    print(f"[OK] Assigned users to shop: {first_shop.name}")
    
    # Create sample job for first shop
    job = Job(
        shop_id=first_shop.id,
        is_active=True,
        hourly_wage='2,500円~5,000円',
        benefits='送迎あり、制服貸与、ノルマなし',
        trial_available=True
    )
    db.session.add(job)
    db.session.commit()
    print(f"[OK] Created job posting for: {first_shop.name}")
    
    # Create sample announcements
    announcements = [
        Announcement(
            title="Night-Walk MVP版をリリースしました！",
            content="岡山・倉敷エリアのナイトスポット検索サービスです。",
            is_active=True,
            priority=10
        ),
        Announcement(
            title="空席情報をリアルタイムで確認できます",
            content="各店舗の空席状況は随時更新されます。",
            is_active=True,
            priority=5
        ),
    ]
    for a in announcements:
        db.session.add(a)
    db.session.commit()
    print("[OK] Created sample announcements")
    
    print("\n" + "="*50)
    print("Database recreated successfully!")
    print("="*50)
    print("\nLogin credentials:")
    print("  Admin:  admin@night-walk.jp / admin123")
    print("  Owner:  owner@example.com / owner123")
    print("  Staff:  staff@example.com / staff123")
