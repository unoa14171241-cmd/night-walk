"""
Night-Walk MVP - Flask Application Factory
"""
from flask import Flask
from .config import config
from .extensions import db, login_manager, migrate, csrf, limiter


def create_app(config_name='default'):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)
    
    # Configure login
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'ログインが必要です。'
    login_manager.login_message_category = 'warning'
    
    # User loader for both User and Customer
    @login_manager.user_loader
    def load_user(user_id):
        """Load user by ID (supports both User and Customer)."""
        from .models import User, Customer
        
        if user_id.startswith('customer_'):
            # カスタマーの場合
            customer_id = int(user_id.replace('customer_', ''))
            return Customer.query.get(customer_id)
        else:
            # 管理者/店舗スタッフの場合
            return User.query.get(int(user_id))
    
    # Register blueprints
    from .routes.auth import auth_bp
    from .routes.admin import admin_bp
    from .routes.shop_admin import shop_admin_bp
    from .routes.public import public_bp
    from .routes.api import api_bp
    from .routes.webhook import webhook_bp
    from .routes.customer import customer_bp
    from .routes.cast import cast_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(shop_admin_bp, url_prefix='/shop')
    app.register_blueprint(public_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(webhook_bp, url_prefix='/webhook')
    app.register_blueprint(customer_bp, url_prefix='/customer')
    app.register_blueprint(cast_bp, url_prefix='/cast')
    
    # Register error handlers
    register_error_handlers(app)
    
    # Context processor for global template variables
    @app.context_processor
    def inject_system_status():
        """Inject system status into all templates."""
        try:
            from .models.system import SystemStatus
            return {'system_status': SystemStatus.get_current_status()}
        except Exception:
            return {'system_status': None}
    
    @app.context_processor
    def inject_seo_context():
        """Inject SEO-related variables into all templates."""
        from flask import request
        
        # noindexにするエンドポイントのプレフィックス
        noindex_prefixes = ['admin.', 'shop_admin.', 'auth.', 'customer.', 'cast.', 'api.', 'webhook.']
        
        # 現在のエンドポイントをチェック
        is_noindex = False
        if request.endpoint:
            for prefix in noindex_prefixes:
                if request.endpoint.startswith(prefix):
                    is_noindex = True
                    break
        
        # BASE_URLを環境変数から取得（sitemap等で使用）
        import os
        base_url = os.environ.get('BASE_URL', request.url_root.rstrip('/') if request else 'https://night-walk-ogrg.onrender.com')
        
        return {
            'seo_noindex': is_noindex,
            'seo_base_url': base_url
        }
    
    # Create database tables
    with app.app_context():
        db.create_all()
        # 既存DB向けの軽量カラム移行（create_allでは既存テーブルへ列追加されないため）
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            if 'shops' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('shops')]
                required_shop_columns = [
                    ('open_time', 'TIME'),
                    ('close_time', 'TIME'),
                    ("business_type", "VARCHAR(30) DEFAULT 'other'"),
                    ('permit_number', 'VARCHAR(100)'),
                ]
                for col_name, col_type in required_shop_columns:
                    if col_name not in columns:
                        db.session.execute(text(f"ALTER TABLE shops ADD COLUMN {col_name} {col_type}"))
                        db.session.commit()
                db.session.execute(text(
                    "UPDATE shops SET business_type = 'other' WHERE business_type IS NULL OR business_type = ''"
                ))
                db.session.commit()
        except Exception:
            db.session.rollback()
    
    return app


def register_error_handlers(app):
    """Register custom error handlers."""
    from flask import render_template, request, jsonify
    
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(429)
    def ratelimit_handler(e):
        """Handle rate limit exceeded."""
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'error': 'Rate limit exceeded',
                'message': 'リクエスト回数が上限を超えました。しばらくしてから再度お試しください。'
            }), 429
        return render_template('errors/429.html'), 429
    
    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return render_template('errors/500.html'), 500
