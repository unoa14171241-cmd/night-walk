"""
Night-Walk MVP - Application Entry Point
"""
from app import create_app
from app.extensions import db
from app.models.user import User, ShopMember
from app.models.shop import Shop, VacancyStatus
from app.models.job import Job
from app.models.billing import Subscription

app = create_app()

def auto_seed():
    """デプロイ時にデータベースが空なら自動でシードデータを作成"""
    with app.app_context():
        # ユーザーが存在するかチェック
        if User.query.first():
            print("[INFO] Database already has data. Skipping auto-seed.")
            return
        
        print("[INFO] Database is empty. Running auto-seed...")
        
        # Create admin user
        admin = User(
            email='admin@night-walk.jp',
            name='管理者',
            role='admin',
        )
        admin.set_password('admin123')
        db.session.add(admin)
        
        # Create sample shop
        shop = Shop(
            name='Club ROYAL',
            area='岡山',
            phone='086-XXX-0001',
            business_hours='20:00〜02:00',
            price_range='5,000円〜',
            description='岡山駅前の人気クラブ。広々とした店内でゆったりとお過ごしいただけます。',
            is_published=True,
        )
        db.session.add(shop)
        db.session.flush()
        
        # Create vacancy status
        vacancy = VacancyStatus(shop_id=shop.id, status='unknown')
        db.session.add(vacancy)
        
        # Create subscription (trial)
        subscription = Subscription(shop_id=shop.id, status='trial')
        db.session.add(subscription)
        
        # Create shop owner user
        owner = User(
            email='owner@example.com',
            name='店舗オーナー',
            role='owner',
        )
        owner.set_password('owner123')
        db.session.add(owner)
        db.session.flush()
        
        # Link owner to shop
        membership = ShopMember(shop_id=shop.id, user_id=owner.id, role='owner')
        db.session.add(membership)
        
        # Create staff user
        staff = User(
            email='staff@example.com',
            name='スタッフ',
            role='staff',
        )
        staff.set_password('staff123')
        db.session.add(staff)
        db.session.flush()
        
        # Link staff to shop
        membership2 = ShopMember(shop_id=shop.id, user_id=staff.id, role='staff')
        db.session.add(membership2)
        
        db.session.commit()
        print("[SUCCESS] Auto-seed completed!")
        print("  Admin:  admin@night-walk.jp / admin123")
        print("  Owner:  owner@example.com / owner123")
        print("  Staff:  staff@example.com / staff123")

# アプリ起動時に自動シード実行
auto_seed()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
