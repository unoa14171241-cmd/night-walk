"""
Night-Walk MVP - Shop Models
"""
from datetime import datetime
from ..extensions import db


class Shop(db.Model):
    """Shop model - store information."""
    __tablename__ = 'shops'
    
    # Areas
    AREA_OKAYAMA = '岡山'
    AREA_KURASHIKI = '倉敷'
    AREAS = [AREA_OKAYAMA, AREA_KURASHIKI]
    
    # Categories (業態)
    CATEGORY_SNACK = 'snack'
    CATEGORY_CONCAFE = 'concafe'
    CATEGORY_GIRLS_BAR = 'girls_bar'
    CATEGORY_KYABAKURA = 'kyabakura'
    CATEGORY_FUZOKU = 'fuzoku'
    CATEGORY_DERIHERU = 'deriheru'
    CATEGORY_LOUNGE = 'lounge'
    CATEGORY_LUXURY_LOUNGE = 'luxury_lounge'
    CATEGORY_CLUB = 'club'
    CATEGORY_BAR = 'bar'
    CATEGORY_MENS_ESTHE = 'mens_esthe'
    CATEGORY_OTHER = 'other'
    
    CATEGORIES = [
        CATEGORY_SNACK, CATEGORY_CONCAFE, CATEGORY_GIRLS_BAR,
        CATEGORY_KYABAKURA, CATEGORY_FUZOKU, CATEGORY_DERIHERU, 
        CATEGORY_LOUNGE, CATEGORY_LUXURY_LOUNGE, CATEGORY_CLUB, 
        CATEGORY_BAR, CATEGORY_MENS_ESTHE, CATEGORY_OTHER
    ]
    CATEGORY_LABELS = {
        CATEGORY_SNACK: 'スナック',
        CATEGORY_CONCAFE: 'コンカフェ',
        CATEGORY_GIRLS_BAR: 'ガールズバー',
        CATEGORY_KYABAKURA: 'キャバクラ',
        CATEGORY_FUZOKU: '風俗',
        CATEGORY_DERIHERU: 'デリヘル',
        CATEGORY_LOUNGE: 'ラウンジ',
        CATEGORY_LUXURY_LOUNGE: '高級ラウンジ',
        CATEGORY_CLUB: 'クラブ',
        CATEGORY_BAR: 'バー',
        CATEGORY_MENS_ESTHE: 'メンズエステ',
        CATEGORY_OTHER: 'その他',
    }
    
    # シーン別グループ（目的別検索用）
    SCENE_LIGHT = 'light'
    SCENE_ENTERTAINMENT = 'entertainment'
    SCENE_ADULT = 'adult'
    
    SCENES = [SCENE_LIGHT, SCENE_ENTERTAINMENT, SCENE_ADULT]
    
    SCENE_GROUPS = {
        SCENE_LIGHT: {
            'name': 'ライトナイト',
            'description': '気軽に飲む・話す',
            'icon': '🍸',
            'color': '#4ECDC4',
            'categories': ['snack', 'concafe', 'girls_bar', 'lounge', 'bar']
        },
        SCENE_ENTERTAINMENT: {
            'name': 'エンタメナイト',
            'description': '盛り上がる・しっかり遊ぶ',
            'icon': '🎉',
            'color': '#FF6B6B',
            'categories': ['kyabakura', 'club', 'luxury_lounge']
        },
        SCENE_ADULT: {
            'name': 'アダルトナイト',
            'description': '大人のサービス',
            'icon': '🌙',
            'color': '#9B59B6',
            'categories': ['fuzoku', 'deriheru', 'mens_esthe']
        }
    }
    
    @classmethod
    def get_categories_by_scene(cls, scene):
        """シーンに含まれるカテゴリリストを取得"""
        if scene in cls.SCENE_GROUPS:
            return cls.SCENE_GROUPS[scene]['categories']
        return []
    
    @classmethod
    def get_scene_for_category(cls, category):
        """カテゴリが属するシーンを取得"""
        for scene, data in cls.SCENE_GROUPS.items():
            if category in data['categories']:
                return scene
        return None
    
    # Price ranges for search
    PRICE_RANGES = [
        (0, 3000, '〜3,000円'),
        (3000, 5000, '3,000円〜5,000円'),
        (5000, 8000, '5,000円〜8,000円'),
        (8000, 10000, '8,000円〜10,000円'),
        (10000, None, '10,000円〜'),
    ]
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    area = db.Column(db.String(50), nullable=False, index=True)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    business_hours = db.Column(db.String(100))  # 例: '20:00-02:00'
    price_range = db.Column(db.String(100))     # 例: '5,000円〜' (表示用)
    price_min = db.Column(db.Integer)           # 最低料金（検索用）
    price_max = db.Column(db.Integer)           # 最高料金（検索用）
    description = db.Column(db.Text)
    image_url = db.Column(db.String(500))       # メイン画像URL（後方互換）
    category = db.Column(db.String(50), nullable=False, index=True)  # 業態カテゴリ（必須）
    tags = db.Column(db.String(500))            # タグ（カンマ区切り）
    is_published = db.Column(db.Boolean, nullable=False, default=False, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    is_featured = db.Column(db.Boolean, nullable=False, default=False)  # おすすめフラグ
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    members = db.relationship('ShopMember', back_populates='shop', lazy='dynamic', cascade='all, delete-orphan')
    vacancy_status = db.relationship('VacancyStatus', back_populates='shop', uselist=False, cascade='all, delete-orphan')
    vacancy_history = db.relationship('VacancyHistory', back_populates='shop', lazy='dynamic', cascade='all, delete-orphan')
    jobs = db.relationship('Job', back_populates='shop', lazy='dynamic', cascade='all, delete-orphan')
    calls = db.relationship('Call', back_populates='shop', lazy='dynamic')
    booking_logs = db.relationship('BookingLog', back_populates='shop', lazy='dynamic')
    subscription = db.relationship('Subscription', back_populates='shop', uselist=False, cascade='all, delete-orphan')
    billing_events = db.relationship('BillingEvent', back_populates='shop', lazy='dynamic')
    inquiries = db.relationship('Inquiry', back_populates='shop', lazy='dynamic')
    images = db.relationship('ShopImage', back_populates='shop', lazy='dynamic', cascade='all, delete-orphan', order_by='ShopImage.sort_order')
    
    @property
    def current_vacancy(self):
        """Get current vacancy status."""
        if self.vacancy_status:
            return self.vacancy_status.status
        return 'unknown'
    
    @property
    def vacancy_updated_at(self):
        """Get vacancy status update time."""
        if self.vacancy_status:
            return self.vacancy_status.updated_at
        return None
    
    @property
    def active_job(self):
        """Get active job posting if any."""
        from .job import Job
        return self.jobs.filter_by(is_active=True).first()
    
    @property
    def is_subscription_active(self):
        """Check if subscription is active."""
        if not self.subscription:
            return False
        return self.subscription.status in ['trial', 'active']
    
    @property
    def main_image(self):
        """Get main image or first image."""
        main = self.images.filter_by(is_main=True).first()
        if main:
            return main
        return self.images.first()
    
    @property
    def main_image_url(self):
        """Get main image URL for display."""
        img = self.main_image
        if img:
            return img.url
        if self.image_url:
            return self.image_url
        return None
    
    @property
    def all_images(self):
        """Get all images ordered by sort_order."""
        return self.images.order_by(ShopImage.sort_order, ShopImage.id).all()
    
    @property
    def category_label(self):
        """Get category display label."""
        return self.CATEGORY_LABELS.get(self.category, '')
    
    @property
    def tags_list(self):
        """Get tags as a list."""
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(',') if t.strip()]
    
    @classmethod
    def get_published(cls, area=None):
        """Get all published and active shops."""
        query = cls.query.filter_by(is_published=True, is_active=True)
        if area:
            query = query.filter_by(area=area)
        return query.order_by(cls.name).all()
    
    @classmethod
    def search(cls, keyword=None, area=None, category=None, scene=None,
               price_range_key=None, vacancy_status=None, has_job=None, featured_only=False):
        """
        Search shops with various filters.
        
        Args:
            keyword: Search keyword (matches name, description, tags)
            area: Area filter
            category: Category filter
            scene: Scene (purpose) filter ('light', 'entertainment', 'adult')
            price_range_key: Price range index (0-4)
            vacancy_status: Vacancy status filter ('empty', 'busy', 'full')
            has_job: Filter for shops with active job postings
            featured_only: Only return featured shops
        """
        query = cls.query.filter_by(is_published=True, is_active=True)
        
        # Keyword search
        if keyword:
            keyword_filter = f'%{keyword}%'
            query = query.filter(
                db.or_(
                    cls.name.ilike(keyword_filter),
                    cls.description.ilike(keyword_filter),
                    cls.tags.ilike(keyword_filter),
                    cls.address.ilike(keyword_filter)
                )
            )
        
        # Area filter
        if area and area in cls.AREAS:
            query = query.filter_by(area=area)
        
        # Scene (purpose) filter - シーンに含まれるカテゴリで絞り込み
        if scene and scene in cls.SCENES:
            scene_categories = cls.get_categories_by_scene(scene)
            if scene_categories:
                query = query.filter(cls.category.in_(scene_categories))
        
        # Category filter (シーン内でさらに絞り込み)
        if category and category in cls.CATEGORIES:
            query = query.filter_by(category=category)
        
        # Price range filter
        if price_range_key is not None:
            try:
                idx = int(price_range_key)
                if 0 <= idx < len(cls.PRICE_RANGES):
                    price_min, price_max, _ = cls.PRICE_RANGES[idx]
                    if price_min > 0:
                        query = query.filter(
                            (cls.price_min == None) | (cls.price_min >= price_min)
                        )
                    if price_max:
                        query = query.filter(
                            (cls.price_max == None) | (cls.price_max <= price_max)
                        )
            except (ValueError, IndexError):
                pass
        
        # Featured only
        if featured_only:
            query = query.filter_by(is_featured=True)
        
        # Get all matching shops
        shops = query.order_by(cls.is_featured.desc(), cls.name).all()
        
        # Post-query filters (requires relationship data)
        if vacancy_status:
            shops = [s for s in shops if s.current_vacancy == vacancy_status]
        
        if has_job:
            shops = [s for s in shops if s.active_job is not None]
        
        return shops
    
    def __repr__(self):
        return f'<Shop {self.name}>'


class VacancyStatus(db.Model):
    """Current vacancy status for a shop (1 record per shop)."""
    __tablename__ = 'vacancy_status'
    
    # Status values
    STATUS_EMPTY = 'empty'    # 空
    STATUS_BUSY = 'busy'      # 混
    STATUS_FULL = 'full'      # 満
    STATUS_UNKNOWN = 'unknown'
    
    STATUSES = [STATUS_EMPTY, STATUS_BUSY, STATUS_FULL, STATUS_UNKNOWN]
    STATUS_LABELS = {
        STATUS_EMPTY: '空',
        STATUS_BUSY: '混',
        STATUS_FULL: '満',
        STATUS_UNKNOWN: '−',
    }
    STATUS_COLORS = {
        STATUS_EMPTY: 'success',   # 緑
        STATUS_BUSY: 'warning',    # 黄
        STATUS_FULL: 'danger',     # 赤
        STATUS_UNKNOWN: 'secondary',
    }
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)
    status = db.Column(db.String(10), nullable=False, default=STATUS_UNKNOWN)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    shop = db.relationship('Shop', back_populates='vacancy_status')
    updater = db.relationship('User', foreign_keys=[updated_by])
    
    @property
    def label(self):
        """Get display label for status."""
        return self.STATUS_LABELS.get(self.status, '−')
    
    @property
    def color(self):
        """Get color class for status."""
        return self.STATUS_COLORS.get(self.status, 'secondary')
    
    def __repr__(self):
        return f'<VacancyStatus shop={self.shop_id} status={self.status}>'


class VacancyHistory(db.Model):
    """Vacancy status change history."""
    __tablename__ = 'vacancies_history'
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)
    status = db.Column(db.String(10), nullable=False)
    changed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    changed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    ip_address = db.Column(db.String(45))
    
    # Relationships
    shop = db.relationship('Shop', back_populates='vacancy_history')
    changer = db.relationship('User', foreign_keys=[changed_by])
    
    def __repr__(self):
        return f'<VacancyHistory shop={self.shop_id} status={self.status}>'


class ShopImage(db.Model):
    """Shop image model for multiple images per shop."""
    __tablename__ = 'shop_images'
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255))  # 元のファイル名
    is_main = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    shop = db.relationship('Shop', back_populates='images')
    
    @property
    def url(self):
        """Get image URL for display."""
        return f'/static/uploads/shops/{self.filename}'
    
    def __repr__(self):
        return f'<ShopImage shop={self.shop_id} file={self.filename}>'
