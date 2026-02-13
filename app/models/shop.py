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
    CATEGORY_LOUNGE = 'lounge'
    CATEGORY_LUXURY_LOUNGE = 'luxury_lounge'
    CATEGORY_CLUB = 'club'
    CATEGORY_BAR = 'bar'
    CATEGORY_MENS_ESTHE = 'mens_esthe'
    CATEGORY_OTHER = 'other'
    
    CATEGORIES = [
        CATEGORY_SNACK, CATEGORY_CONCAFE, CATEGORY_GIRLS_BAR,
        CATEGORY_KYABAKURA, CATEGORY_LOUNGE, CATEGORY_LUXURY_LOUNGE, 
        CATEGORY_CLUB, CATEGORY_BAR, CATEGORY_MENS_ESTHE, CATEGORY_OTHER
    ]
    CATEGORY_LABELS = {
        CATEGORY_SNACK: 'スナック',
        CATEGORY_CONCAFE: 'コンカフェ',
        CATEGORY_GIRLS_BAR: 'ガールズバー',
        CATEGORY_KYABAKURA: 'キャバクラ',
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
    
    SCENES = [SCENE_LIGHT, SCENE_ENTERTAINMENT]
    
    SCENE_GROUPS = {
        SCENE_LIGHT: {
            'name': 'ライトナイト',
            'description': '一人飲み・軽く一杯・会話中心',
            'categories_display': 'スナック / バー / 立ち飲み',
            'price_range': '3,000〜6,000円目安',
            'color': '#10b981',
            'categories': ['snack', 'concafe', 'girls_bar', 'lounge', 'bar']
        },
        SCENE_ENTERTAINMENT: {
            'name': 'エンタメナイト',
            'description': '複数人・盛り上がりたい夜',
            'categories_display': 'キャバクラ / コンカフェ / ガールズバー',
            'price_range': '6,000〜15,000円目安',
            'color': '#ef4444',
            'categories': ['kyabakura', 'club', 'luxury_lounge', 'concafe', 'girls_bar', 'mens_esthe']
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
    
    # 審査ステータス
    STATUS_PENDING = 'pending'      # 仮登録（審査待ち）
    STATUS_APPROVED = 'approved'    # 承認済み
    STATUS_REJECTED = 'rejected'    # 却下
    
    STATUS_LABELS = {
        STATUS_PENDING: '審査待ち',
        STATUS_APPROVED: '承認済み',
        STATUS_REJECTED: '却下',
    }
    
    # 振込サイクル
    PAYOUT_CYCLE_MONTH_END = 'month_end'  # 月末締め
    PAYOUT_CYCLES = [PAYOUT_CYCLE_MONTH_END]
    
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
    is_demo = db.Column(db.Boolean, nullable=False, default=False)  # デモアカウント用店舗
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 審査フロー関連
    review_status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING, index=True)
    reviewed_at = db.Column(db.DateTime)        # 審査完了日時
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))  # 審査担当者
    review_notes = db.Column(db.Text)           # 審査メモ
    
    # 振込サイクル設定
    payout_cycle = db.Column(db.String(20), default=PAYOUT_CYCLE_MONTH_END)  # 締め日タイプ
    payout_day = db.Column(db.Integer, default=5)  # 翌月○営業日払い
    
    # キャンペーン設定
    campaign_free_months = db.Column(db.Integer, default=0)  # 無料期間（月数）
    campaign_start_date = db.Column(db.Date)     # キャンペーン開始日
    campaign_notes = db.Column(db.Text)          # 特別条件（任意テキスト）
    
    # 振込口座情報
    bank_name = db.Column(db.String(100), nullable=True)        # 金融機関名
    bank_branch = db.Column(db.String(100), nullable=True)      # 支店名
    account_type = db.Column(db.String(20), nullable=True)      # 口座種別（普通/当座）
    account_number = db.Column(db.String(20), nullable=True)    # 口座番号
    account_holder = db.Column(db.String(100), nullable=True)   # 口座名義（カタカナ）
    
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
    def review_status_label(self):
        """Get review status display label."""
        return self.STATUS_LABELS.get(self.review_status, self.review_status)
    
    @property
    def is_approved(self):
        """Check if shop is approved."""
        return self.review_status == self.STATUS_APPROVED
    
    @property
    def is_pending_review(self):
        """Check if shop is pending review."""
        return self.review_status == self.STATUS_PENDING
    
    @property
    def can_login(self):
        """Check if shop owners/staff can login (approved and active)."""
        return self.is_approved and self.is_active
    
    def approve(self, reviewer_id=None, notes=None):
        """Approve the shop and enable login."""
        self.review_status = self.STATUS_APPROVED
        self.reviewed_at = datetime.utcnow()
        self.reviewed_by = reviewer_id
        self.review_notes = notes
        self.is_published = True  # 自動公開
    
    def reject(self, reviewer_id=None, notes=None):
        """Reject the shop."""
        self.review_status = self.STATUS_REJECTED
        self.reviewed_at = datetime.utcnow()
        self.reviewed_by = reviewer_id
        self.review_notes = notes
        self.is_published = False
    
    def get_next_payout_date(self, reference_date=None):
        """
        次回振込日を計算する。
        Args:
            reference_date: 基準日（デフォルト: 今日）
        Returns:
            date: 次回振込予定日
        """
        from datetime import date, timedelta
        import calendar
        
        if reference_date is None:
            reference_date = date.today()
        
        # 月末締め→翌月○営業日払い
        # まず翌月1日を取得
        if reference_date.month == 12:
            next_month = date(reference_date.year + 1, 1, 1)
        else:
            next_month = date(reference_date.year, reference_date.month + 1, 1)
        
        # ○営業日後を計算（土日を除く）
        business_days = 0
        payout_date = next_month
        while business_days < (self.payout_day or 5):
            if payout_date.weekday() < 5:  # 月〜金
                business_days += 1
            if business_days < (self.payout_day or 5):
                payout_date += timedelta(days=1)
        
        return payout_date
    
    @property
    def is_in_free_period(self):
        """Check if shop is in free campaign period."""
        from datetime import date
        if not self.campaign_free_months or self.campaign_free_months <= 0:
            return False
        if not self.campaign_start_date:
            return False
        
        today = date.today()
        # キャンペーン終了月を計算
        end_year = self.campaign_start_date.year
        end_month = self.campaign_start_date.month + self.campaign_free_months
        while end_month > 12:
            end_month -= 12
            end_year += 1
        
        from calendar import monthrange
        last_day = monthrange(end_year, end_month)[1]
        end_date = date(end_year, end_month, last_day)
        
        return today <= end_date
    
    @property
    def free_period_end_date(self):
        """Get free period end date."""
        from datetime import date
        from calendar import monthrange
        
        if not self.campaign_free_months or not self.campaign_start_date:
            return None
        
        end_year = self.campaign_start_date.year
        end_month = self.campaign_start_date.month + self.campaign_free_months
        while end_month > 12:
            end_month -= 12
            end_year += 1
        
        last_day = monthrange(end_year, end_month)[1]
        return date(end_year, end_month, last_day)
    
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
    
    # 不適切コンテンツ対策
    is_hidden = db.Column(db.Boolean, default=False)  # 管理者による非表示
    hidden_at = db.Column(db.DateTime)
    hidden_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    hidden_reason = db.Column(db.String(200))
    
    # Relationships
    shop = db.relationship('Shop', back_populates='images')
    
    @property
    def url(self):
        """Get image URL for display."""
        return f'/static/uploads/shops/{self.filename}'
    
    @property
    def is_visible(self):
        """表示可能かどうか"""
        return not self.is_hidden
    
    def hide(self, user_id, reason=None):
        """画像を非表示にする"""
        self.is_hidden = True
        self.hidden_at = datetime.utcnow()
        self.hidden_by = user_id
        self.hidden_reason = reason
    
    def unhide(self):
        """非表示を解除"""
        self.is_hidden = False
        self.hidden_at = None
        self.hidden_by = None
        self.hidden_reason = None
    
    def __repr__(self):
        return f'<ShopImage shop={self.shop_id} file={self.filename}>'
