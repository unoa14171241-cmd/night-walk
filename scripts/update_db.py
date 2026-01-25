"""
Update database - Add new tables (ShopImage, Announcement, Advertisement)
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import *

app = create_app('development')

with app.app_context():
    # Create all new tables
    db.create_all()
    print("[OK] Database tables updated!")
    
    # Add sample announcements
    if Announcement.query.count() == 0:
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
        print("[OK] Sample announcements created!")
    
    # Update existing shops with sample data
    shops = Shop.query.all()
    categories = ['lounge', 'club', 'bar', 'snack', 'other']
    
    for i, shop in enumerate(shops):
        if not shop.category:
            shop.category = categories[i % len(categories)]
        if not shop.tags:
            tags = []
            if i % 2 == 0:
                tags.append("駅近")
            if i % 3 == 0:
                tags.append("カラオケあり")
            if i % 4 == 0:
                tags.append("個室あり")
            shop.tags = ','.join(tags) if tags else None
        if shop.price_range and not shop.price_min:
            # Set default price range for search
            shop.price_min = 3000 + (i * 1000)
            shop.price_max = 8000 + (i * 1000)
        shop.is_featured = (i == 0)  # First shop is featured
    
    db.session.commit()
    print("[OK] Shop data updated with categories and tags!")
    
    print("\nDatabase update completed!")
