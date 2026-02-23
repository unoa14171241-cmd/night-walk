#!/usr/bin/env python
"""
Night-Walk - Add Point & Gift System Tables and Seed Data

Usage:
    python scripts/add_point_gift_system.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import (
    Customer, PointPackage, PointTransaction,
    Cast, Gift, GiftTransaction, Earning, Shop
)


def seed_point_packages():
    """Seed point packages."""
    packages = [
        {'name': 'ライト', 'price': 500, 'points': 500, 'bonus_points': 0, 'sort_order': 1},
        {'name': 'スタンダード', 'price': 1000, 'points': 1000, 'bonus_points': 0, 'sort_order': 2},
        {'name': 'お得パック', 'price': 3000, 'points': 3000, 'bonus_points': 300, 'sort_order': 3, 'is_featured': True},
        {'name': 'バリューパック', 'price': 5000, 'points': 5000, 'bonus_points': 500, 'sort_order': 4},
        {'name': 'プレミアムパック', 'price': 10000, 'points': 10000, 'bonus_points': 2000, 'sort_order': 5, 'is_featured': True},
        {'name': 'VIPパック', 'price': 30000, 'points': 30000, 'bonus_points': 10000, 'sort_order': 6},
    ]
    
    for pkg_data in packages:
        existing = PointPackage.query.filter_by(name=pkg_data['name']).first()
        if not existing:
            pkg = PointPackage(**pkg_data)
            db.session.add(pkg)
            print(f"  [OK] PointPackage: {pkg_data['name']}")
        else:
            print(f"  [SKIP] PointPackage: {pkg_data['name']} (already exists)")
    
    db.session.commit()


def seed_gifts():
    """Seed gifts."""
    gifts = [
        {
            'name': 'ライト',
            'description': '気軽に送れるギフト',
            'points': 100,
            'cast_rate': 40,
            'shop_rate': 30,
            'platform_rate': 30,
            'sort_order': 1
        },
        {
            'name': 'スタンダード',
            'description': '定番のギフト',
            'points': 500,
            'cast_rate': 40,
            'shop_rate': 30,
            'platform_rate': 30,
            'sort_order': 2
        },
        {
            'name': 'スペシャル',
            'description': '特別な応援に',
            'points': 1000,
            'cast_rate': 40,
            'shop_rate': 30,
            'platform_rate': 30,
            'sort_order': 3
        },
        {
            'name': 'プレミアム',
            'description': '本気の応援',
            'points': 5000,
            'cast_rate': 40,
            'shop_rate': 30,
            'platform_rate': 30,
            'sort_order': 4
        },
        {
            'name': 'ラグジュアリー',
            'description': '最高級ギフト',
            'points': 10000,
            'cast_rate': 40,
            'shop_rate': 30,
            'platform_rate': 30,
            'sort_order': 5
        },
        {
            'name': 'ゴッド',
            'description': '伝説のギフト',
            'points': 30000,
            'cast_rate': 40,
            'shop_rate': 30,
            'platform_rate': 30,
            'sort_order': 6
        },
    ]
    
    for gift_data in gifts:
        existing = Gift.query.filter_by(name=gift_data['name']).first()
        if not existing:
            gift = Gift(**gift_data)
            db.session.add(gift)
            print(f"  [OK] Gift: {gift_data['name']} ({gift_data['points']}pt)")
        else:
            print(f"  [SKIP] Gift: {gift_data['name']} (already exists)")
    
    db.session.commit()


def seed_sample_casts():
    """Seed sample casts for existing shops."""
    shops = Shop.query.filter_by(is_active=True).all()
    
    sample_casts = [
        {'name': 'みゆき', 'display_name': 'MIYUKI', 'profile': 'よろしくお願いします!'},
        {'name': 'さくら', 'display_name': 'SAKURA', 'profile': '一緒に楽しい時間を過ごしましょう'},
        {'name': 'れいな', 'display_name': 'REINA', 'profile': 'お待ちしています'},
    ]
    
    for shop in shops:
        existing_count = Cast.query.filter_by(shop_id=shop.id).count()
        if existing_count == 0:
            for i, cast_data in enumerate(sample_casts):
                cast = Cast(
                    shop_id=shop.id,
                    name=cast_data['name'],
                    display_name=cast_data['display_name'],
                    profile=cast_data['profile'],
                    is_active=True,
                    is_accepting_gifts=True,
                    sort_order=i
                )
                db.session.add(cast)
            print(f"  [OK] Added 3 sample casts to: {shop.name}")
        else:
            print(f"  [SKIP] {shop.name} already has casts")
    
    db.session.commit()


def seed_test_customer():
    """Seed a test customer."""
    email = 'customer@example.com'
    existing = Customer.query.filter_by(email=email).first()
    
    if not existing:
        customer = Customer(
            email=email,
            nickname='テストユーザー',
            point_balance=10000,  # Give some test points
            is_active=True,
            is_verified=True
        )
        customer.set_password('customer123')
        db.session.add(customer)
        db.session.commit()
        print(f"  [OK] Test customer: {email} / customer123 (10000pt)")
    else:
        print(f"  [SKIP] Test customer already exists")


def main():
    """Main function."""
    app = create_app()
    
    with app.app_context():
        print("\n=== Night-Walk: Adding Point & Gift System ===\n")
        
        # Create tables
        print("[1/5] Creating tables...")
        db.create_all()
        print("  [OK] Tables created")
        
        # Seed point packages
        print("\n[2/5] Seeding point packages...")
        seed_point_packages()
        
        # Seed gifts
        print("\n[3/5] Seeding gifts...")
        seed_gifts()
        
        # Seed sample casts
        print("\n[4/5] Seeding sample casts...")
        seed_sample_casts()
        
        # Seed test customer
        print("\n[5/5] Seeding test customer...")
        seed_test_customer()
        
        print("\n=== Complete! ===\n")
        print("Test customer login:")
        print("  Email: customer@example.com")
        print("  Password: customer123")
        print("  Points: 10,000pt")


if __name__ == '__main__':
    main()
