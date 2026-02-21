# wsgi.py
"""WSGI entry point for production (Gunicorn)"""

import os
import logging
from app import create_app
from app.extensions import db
from app.models.user import User, ShopMember
from app.models.shop import Shop, VacancyStatus
from app.models.billing import Subscription

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = create_app('production')


# ============================================
# Scheduled Jobs (APScheduler)
# ============================================

def setup_scheduler():
    """APSchedulerを設定してジョブを登録"""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger
        
        scheduler = BackgroundScheduler()
        
        # 急上昇更新ジョブ（15分ごと）
        def run_trending_job():
            with app.app_context():
                from app.jobs.trending_job import update_trending
                update_trending()
        
        scheduler.add_job(
            run_trending_job,
            IntervalTrigger(minutes=15),
            id='update_trending',
            name='Update Trending Data',
            replace_existing=True
        )
        
        # 月次ランキング確定ジョブ（毎月1日 0:00 JST）
        def run_ranking_job():
            with app.app_context():
                from app.jobs.ranking_job import finalize_monthly_rankings
                finalize_monthly_rankings(auto_entitlements=True)
        
        scheduler.add_job(
            run_ranking_job,
            CronTrigger(day=1, hour=0, minute=0, timezone='Asia/Tokyo'),
            id='finalize_rankings',
            name='Finalize Monthly Rankings',
            replace_existing=True
        )
        
        # プラン権利同期ジョブ（毎日 3:00 JST）
        def run_plan_sync_job():
            with app.app_context():
                from app.jobs.ranking_job import sync_plan_entitlements
                sync_plan_entitlements()
        
        scheduler.add_job(
            run_plan_sync_job,
            CronTrigger(hour=3, minute=0, timezone='Asia/Tokyo'),
            id='sync_plan_entitlements',
            name='Sync Plan Entitlements',
            replace_existing=True
        )
        
        # PVクリーンアップジョブ（毎日 4:00 JST）
        def run_cleanup_job():
            with app.app_context():
                from app.jobs.trending_job import cleanup_old_page_views
                cleanup_old_page_views()
        
        scheduler.add_job(
            run_cleanup_job,
            CronTrigger(hour=4, minute=0, timezone='Asia/Tokyo'),
            id='cleanup_page_views',
            name='Cleanup Old Page Views',
            replace_existing=True
        )
        
        # 遅刻キャンセルジョブ（毎分実行）
        def run_late_cancellation_job():
            with app.app_context():
                from app.jobs.booking_job import process_late_cancellations
                process_late_cancellations()
        
        scheduler.add_job(
            run_late_cancellation_job,
            IntervalTrigger(minutes=1),
            id='late_cancellation',
            name='Process Late Cancellations',
            replace_existing=True
        )
        
        scheduler.start()
        logger.info("[SCHEDULER] APScheduler started with %d jobs", len(scheduler.get_jobs()))
        
        return scheduler
        
    except ImportError:
        logger.warning("[SCHEDULER] APScheduler not installed. Scheduled jobs disabled.")
        return None
    except Exception as e:
        logger.error("[SCHEDULER] Failed to setup scheduler: %s", e)
        return None


# Production環境でのみスケジューラを起動
if os.environ.get('FLASK_ENV') == 'production' or os.environ.get('ENABLE_SCHEDULER') == '1':
    scheduler = setup_scheduler()

def auto_create_tables():
    """起動時に存在しないテーブルを自動作成"""
    with app.app_context():
        try:
            # 全モデルをインポートしてテーブルを作成
            from app import models  # noqa: F401
            # システム管理モデルを明示的にインポート
            from app.models.system import SystemStatus, ContentReport, SystemLog, DemoAccount  # noqa: F401
            from app.models.email_template import EmailTemplate  # noqa: F401
            from app.models.blog import BlogPost  # noqa: F401
            db.create_all()
            print("[INFO] Database tables checked/created successfully.")
        except Exception as e:
            print(f"[WARNING] Table creation error (may be normal): {e}")


def auto_migrate_columns():
    """起動時に不足しているカラムを自動追加"""
    with app.app_context():
        try:
            from sqlalchemy import text, inspect
            
            inspector = inspect(db.engine)
            
            # customersテーブルのカラムをチェック
            if 'customers' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('customers')]
                
                # phone_numberカラムが存在しない場合は追加
                if 'phone_number' not in columns:
                    print("[INFO] Adding 'phone_number' column to customers table...")
                    db.session.execute(text(
                        "ALTER TABLE customers ADD COLUMN phone_number VARCHAR(20)"
                    ))
                    db.session.commit()
                    print("[SUCCESS] 'phone_number' column added to customers table!")
                
                # phone_verifiedカラムが存在しない場合は追加
                if 'phone_verified' not in columns:
                    print("[INFO] Adding 'phone_verified' column to customers table...")
                    db.session.execute(text(
                        "ALTER TABLE customers ADD COLUMN phone_verified BOOLEAN DEFAULT FALSE"
                    ))
                    db.session.commit()
                    print("[SUCCESS] 'phone_verified' column added to customers table!")
            
            # shopsテーブルのカラムをチェック（審査フロー・振込サイクル・キャンペーン）
            if 'shops' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('shops')]
                
                shop_columns = [
                    ("review_status", "VARCHAR(20) DEFAULT 'approved'"),
                    ("reviewed_at", "TIMESTAMP"),
                    ("reviewed_by", "INTEGER"),
                    ("review_notes", "TEXT"),
                    ("payout_cycle", "VARCHAR(20) DEFAULT 'month_end'"),
                    ("payout_day", "INTEGER DEFAULT 5"),
                    ("campaign_free_months", "INTEGER DEFAULT 0"),
                    ("campaign_start_date", "DATE"),
                    ("campaign_notes", "TEXT"),
                    # 振込口座情報
                    ("bank_name", "VARCHAR(100)"),
                    ("bank_branch", "VARCHAR(100)"),
                    ("account_type", "VARCHAR(20)"),
                    ("account_number", "VARCHAR(20)"),
                    ("account_holder", "VARCHAR(100)"),
                    # SEOスラッグ
                    ("slug", "VARCHAR(200)"),
                ]
                
                for col_name, col_type in shop_columns:
                    if col_name not in columns:
                        print(f"[INFO] Adding '{col_name}' column to shops table...")
                        db.session.execute(text(
                            f"ALTER TABLE shops ADD COLUMN {col_name} {col_type}"
                        ))
                        db.session.commit()
                        print(f"[SUCCESS] '{col_name}' column added to shops table!")
            
            # castsテーブルのカラムをチェック（キャストログイン・出勤状況）
            if 'casts' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('casts')]
                
                cast_columns = [
                    ("comment", "VARCHAR(200)"),
                    ("work_status", "VARCHAR(20) DEFAULT 'off'"),
                    ("work_start_time", "VARCHAR(5)"),
                    ("work_end_time", "VARCHAR(5)"),
                    ("work_memo", "VARCHAR(100)"),
                    ("login_code", "VARCHAR(8)"),
                    ("pin_hash", "VARCHAR(255)"),
                    ("last_login_at", "TIMESTAMP"),
                    ("is_visible", "BOOLEAN DEFAULT TRUE"),
                    ("monthly_gift_goal", "INTEGER DEFAULT 0"),
                    ("monthly_gift_goal_message", "VARCHAR(200)"),
                    ("show_gift_progress", "BOOLEAN DEFAULT FALSE"),
                    # キャストプロフィール拡張
                    ("age", "INTEGER"),
                    ("tiktok_url", "VARCHAR(255)"),
                    ("video_url", "VARCHAR(255)"),
                    ("gift_appeal", "TEXT"),
                    # SEOスラッグ
                    ("slug", "VARCHAR(200)"),
                ]
                
                for col_name, col_type in cast_columns:
                    if col_name not in columns:
                        print(f"[INFO] Adding '{col_name}' column to casts table...")
                        try:
                            db.session.execute(text(
                                f"ALTER TABLE casts ADD COLUMN {col_name} {col_type}"
                            ))
                            db.session.commit()
                            print(f"[SUCCESS] '{col_name}' column added to casts table!")
                        except Exception as col_e:
                            print(f"[WARNING] Failed to add '{col_name}': {col_e}")
                            db.session.rollback()
            
            # shop_imagesテーブルのカラムをチェック（不適切コンテンツ対策）
            if 'shop_images' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('shop_images')]
                
                image_columns = [
                    ("is_hidden", "BOOLEAN DEFAULT FALSE"),
                    ("hidden_at", "TIMESTAMP"),
                    ("hidden_by", "INTEGER"),
                    ("hidden_reason", "VARCHAR(200)"),
                ]
                
                for col_name, col_type in image_columns:
                    if col_name not in columns:
                        print(f"[INFO] Adding '{col_name}' column to shop_images table...")
                        try:
                            db.session.execute(text(
                                f"ALTER TABLE shop_images ADD COLUMN {col_name} {col_type}"
                            ))
                            db.session.commit()
                            print(f"[SUCCESS] '{col_name}' column added to shop_images table!")
                        except Exception as col_e:
                            print(f"[WARNING] Failed to add '{col_name}': {col_e}")
                            db.session.rollback()
            
            # shopsテーブルにis_demoカラムを追加
            if 'shops' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('shops')]
                if 'is_demo' not in columns:
                    print("[INFO] Adding 'is_demo' column to shops table...")
                    try:
                        db.session.execute(text(
                            "ALTER TABLE shops ADD COLUMN is_demo BOOLEAN DEFAULT FALSE"
                        ))
                        db.session.commit()
                        print("[SUCCESS] 'is_demo' column added to shops table!")
                    except Exception as col_e:
                        print(f"[WARNING] Failed to add 'is_demo': {col_e}")
                        db.session.rollback()
            
            # booking_logsテーブルのカラムをチェック（直前限定予約・指名キャスト）
            if 'booking_logs' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('booking_logs')]
                
                booking_columns = [
                    ("cast_id", "INTEGER"),
                    ("customer_id", "INTEGER"),
                    ("customer_phone", "VARCHAR(20)"),
                    ("customer_name", "VARCHAR(100)"),
                    ("party_size", "INTEGER DEFAULT 1"),
                    ("scheduled_at", "TIMESTAMP"),
                    ("cancelled_at", "TIMESTAMP"),
                    ("cancel_reason", "VARCHAR(255)"),
                    ("checked_in_at", "TIMESTAMP"),
                    ("updated_at", "TIMESTAMP"),
                ]
                
                for col_name, col_type in booking_columns:
                    if col_name not in columns:
                        print(f"[INFO] Adding '{col_name}' column to booking_logs table...")
                        try:
                            db.session.execute(text(
                                f"ALTER TABLE booking_logs ADD COLUMN {col_name} {col_type}"
                            ))
                            db.session.commit()
                            print(f"[SUCCESS] '{col_name}' column added to booking_logs table!")
                        except Exception as col_e:
                            print(f"[WARNING] Failed to add '{col_name}': {col_e}")
                            db.session.rollback()
                    
            # shop_point_cardsテーブルにカラムを追加（スタンプカード対応）
            if 'shop_point_cards' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('shop_point_cards')]
                spc_columns = [
                    ("rank_system_enabled", "BOOLEAN DEFAULT FALSE"),
                    ("card_image_url", "VARCHAR(500)"),
                    ("max_stamps", "INTEGER DEFAULT 10"),
                    ("card_template", "VARCHAR(30) DEFAULT 'bronze'"),
                    ("show_stamp_numbers", "BOOLEAN DEFAULT TRUE"),
                ]
                for col_name, col_type in spc_columns:
                    if col_name not in columns:
                        print(f"[INFO] Adding '{col_name}' column to shop_point_cards table...")
                        try:
                            db.session.execute(text(
                                f"ALTER TABLE shop_point_cards ADD COLUMN {col_name} {col_type}"
                            ))
                            db.session.commit()
                            print(f"[SUCCESS] '{col_name}' column added!")
                        except Exception as col_e:
                            print(f"[WARNING] Failed to add '{col_name}': {col_e}")
                            db.session.rollback()
            
            # shop_point_ranksテーブルにcard_templateカラムを追加
            if 'shop_point_ranks' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('shop_point_ranks')]
                spr_columns = [
                    ("card_template", "VARCHAR(30) DEFAULT 'bronze'"),
                ]
                for col_name, col_type in spr_columns:
                    if col_name not in columns:
                        print(f"[INFO] Adding '{col_name}' column to shop_point_ranks table...")
                        try:
                            db.session.execute(text(
                                f"ALTER TABLE shop_point_ranks ADD COLUMN {col_name} {col_type}"
                            ))
                            db.session.commit()
                            print(f"[SUCCESS] '{col_name}' column added!")
                        except Exception as col_e:
                            print(f"[WARNING] Failed to add '{col_name}': {col_e}")
                            db.session.rollback()
            
            # customer_shop_pointsテーブルにカラムを追加
            if 'customer_shop_points' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('customer_shop_points')]
                csp_columns = [
                    ("current_rank_id", "INTEGER"),
                    ("current_rank_name", "VARCHAR(50)"),
                    ("current_rank_icon", "VARCHAR(10)"),
                    ("visit_count", "INTEGER DEFAULT 0"),
                    ("total_earned", "INTEGER DEFAULT 0"),
                    ("total_used", "INTEGER DEFAULT 0"),
                    ("last_visit_at", "TIMESTAMP"),
                ]
                for col_name, col_type in csp_columns:
                    if col_name not in columns:
                        print(f"[INFO] Adding '{col_name}' column to customer_shop_points table...")
                        try:
                            db.session.execute(text(
                                f"ALTER TABLE customer_shop_points ADD COLUMN {col_name} {col_type}"
                            ))
                            db.session.commit()
                            print(f"[SUCCESS] '{col_name}' column added!")
                        except Exception as col_e:
                            print(f"[WARNING] Failed to add '{col_name}': {col_e}")
                            db.session.rollback()
            
            # shop_point_transactionsテーブルにカラムを追加
            if 'shop_point_transactions' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('shop_point_transactions')]
                spt_columns = [
                    ("verification_method", "VARCHAR(20)"),
                    ("verified_by", "INTEGER"),
                ]
                for col_name, col_type in spt_columns:
                    if col_name not in columns:
                        print(f"[INFO] Adding '{col_name}' column to shop_point_transactions table...")
                        try:
                            db.session.execute(text(
                                f"ALTER TABLE shop_point_transactions ADD COLUMN {col_name} {col_type}"
                            ))
                            db.session.commit()
                            print(f"[SUCCESS] '{col_name}' column added!")
                        except Exception as col_e:
                            print(f"[WARNING] Failed to add '{col_name}': {col_e}")
                            db.session.rollback()
            
        except Exception as e:
            print(f"[WARNING] Column migration error: {e}")
            db.session.rollback()


# アプリ起動時にテーブル自動作成
auto_create_tables()

# 不足カラムの自動マイグレーション
auto_migrate_columns()


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
            category='club',
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


def auto_seed_point_packages():
    """ポイントパッケージ・ギフトが存在しなければ自動で追加"""
    with app.app_context():
        from app.models import PointPackage, Gift
        
        # ポイントパッケージが0件なら追加
        if PointPackage.query.count() == 0:
            print("[INFO] Seeding point packages...")
            packages = [
                {'name': 'ライト', 'price': 500, 'points': 500, 'bonus_points': 0, 'sort_order': 1},
                {'name': 'スタンダード', 'price': 1000, 'points': 1000, 'bonus_points': 0, 'sort_order': 2},
                {'name': 'お得パック', 'price': 3000, 'points': 3000, 'bonus_points': 300, 'sort_order': 3, 'is_featured': True},
                {'name': 'バリューパック', 'price': 5000, 'points': 5000, 'bonus_points': 500, 'sort_order': 4},
                {'name': 'プレミアムパック', 'price': 10000, 'points': 10000, 'bonus_points': 2000, 'sort_order': 5, 'is_featured': True},
                {'name': 'VIPパック', 'price': 30000, 'points': 30000, 'bonus_points': 10000, 'sort_order': 6},
            ]
            for pkg_data in packages:
                db.session.add(PointPackage(**pkg_data))
            db.session.commit()
            print("[SUCCESS] Point packages seeded!")
        
        # ギフトが0件なら追加
        if Gift.query.count() == 0:
            print("[INFO] Seeding gifts...")
            gifts = [
                {'name': 'ライト', 'description': '気軽に送れるギフト', 'points': 100, 'cast_rate': 50, 'shop_rate': 20, 'platform_rate': 30, 'sort_order': 1},
                {'name': 'スタンダード', 'description': '定番のギフト', 'points': 500, 'cast_rate': 50, 'shop_rate': 20, 'platform_rate': 30, 'sort_order': 2},
                {'name': 'スペシャル', 'description': '特別な応援に', 'points': 1000, 'cast_rate': 50, 'shop_rate': 20, 'platform_rate': 30, 'sort_order': 3},
                {'name': 'プレミアム', 'description': '本気の応援', 'points': 5000, 'cast_rate': 50, 'shop_rate': 20, 'platform_rate': 30, 'sort_order': 4},
                {'name': 'ラグジュアリー', 'description': '最高級ギフト', 'points': 10000, 'cast_rate': 50, 'shop_rate': 20, 'platform_rate': 30, 'sort_order': 5},
                {'name': 'ゴッド', 'description': '伝説のギフト', 'points': 30000, 'cast_rate': 50, 'shop_rate': 20, 'platform_rate': 30, 'sort_order': 6},
            ]
            for gift_data in gifts:
                db.session.add(Gift(**gift_data))
            db.session.commit()
            print("[SUCCESS] Gifts seeded!")


def auto_seed_blog():
    """ブログ記事の自動シード"""
    with app.app_context():
        try:
            from app.models.blog import BlogPost
            BlogPost.seed_posts()
            print("[INFO] Blog posts seeded (if needed).")
        except Exception as e:
            print(f"[WARNING] Blog seed error: {e}")


def auto_generate_slugs():
    """既存の店舗・キャストにスラッグを自動生成"""
    with app.app_context():
        try:
            import re
            from sqlalchemy import text

            def make_slug(name, id_val, prefix=''):
                s = re.sub(r'[^\w\s-]', '', name.lower().strip())
                s = re.sub(r'[\s_]+', '-', s)
                s = re.sub(r'-+', '-', s).strip('-')
                if not s or not re.search(r'[a-z0-9]', s):
                    s = f'{prefix}{id_val}'
                return f'{s}-{id_val}'

            shops_without_slug = Shop.query.filter(
                (Shop.slug == None) | (Shop.slug == '')
            ).all()
            for shop in shops_without_slug:
                shop.slug = make_slug(shop.name, shop.id, 'shop-')
            if shops_without_slug:
                db.session.commit()
                print(f"[INFO] Generated slugs for {len(shops_without_slug)} shops.")

            from app.models.gift import Cast
            casts_without_slug = Cast.query.filter(
                (Cast.slug == None) | (Cast.slug == '')
            ).all()
            for cast in casts_without_slug:
                display = cast.display_name or cast.name
                cast.slug = make_slug(display, cast.id, 'cast-')
            if casts_without_slug:
                db.session.commit()
                print(f"[INFO] Generated slugs for {len(casts_without_slug)} casts.")

        except Exception as e:
            print(f"[WARNING] Slug generation error: {e}")
            db.session.rollback()


# ポイントパッケージ・ギフトの自動シード
auto_seed_point_packages()
auto_seed_blog()
auto_generate_slugs()

if __name__ == '__main__':
    app.run()
