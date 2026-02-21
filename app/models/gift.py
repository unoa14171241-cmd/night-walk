# app/models/gift.py
"""ギフト・キャスト関連モデル"""

from datetime import datetime
from flask import url_for
from werkzeug.security import generate_password_hash, check_password_hash
from ..extensions import db
import secrets


class Cast(db.Model):
    """キャスト"""
    __tablename__ = 'casts'
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)
    
    name = db.Column(db.String(50), nullable=False)
    slug = db.Column(db.String(200), unique=True, index=True)
    display_name = db.Column(db.String(50))  # 源氏名・表示名
    age = db.Column(db.Integer)  # 年齢
    profile = db.Column(db.Text)  # 自己紹介
    comment = db.Column(db.String(200))  # 本日のコメント（キャスト更新可能）
    image_filename = db.Column(db.String(255))
    
    # ショート動画
    video_url = db.Column(db.String(500))  # ショート動画URL（YouTube Shorts, TikTok, Instagram Reels等）
    
    # ギフトへの意気込み
    gift_appeal = db.Column(db.Text)  # ギフト（投げ銭）への意気込み自由記述
    
    # 出勤状況
    WORK_STATUS_OFF = 'off'           # 休み
    WORK_STATUS_WORKING = 'working'   # 出勤中
    WORK_STATUS_SCHEDULED = 'scheduled'  # 出勤予定
    
    work_status = db.Column(db.String(20), default=WORK_STATUS_OFF)
    work_start_time = db.Column(db.String(5))  # 出勤開始時間 (HH:MM)
    work_end_time = db.Column(db.String(5))    # 出勤終了時間 (HH:MM)
    work_memo = db.Column(db.String(100))       # 出勤メモ
    
    # キャストログイン用
    login_code = db.Column(db.String(8), unique=True, index=True)  # 8桁ログインコード
    pin_hash = db.Column(db.String(255))  # 4桁PIN（ハッシュ化）
    last_login_at = db.Column(db.DateTime)
    
    # SNS
    twitter_url = db.Column(db.String(255))
    instagram_url = db.Column(db.String(255))
    tiktok_url = db.Column(db.String(255))
    
    is_active = db.Column(db.Boolean, default=True)
    is_visible = db.Column(db.Boolean, default=True)  # プロフィールページを公開するか
    is_accepting_gifts = db.Column(db.Boolean, default=True)  # ギフト受付中
    is_featured = db.Column(db.Boolean, default=False)  # 注目キャスト
    
    # 累計
    total_gifts_received = db.Column(db.Integer, default=0)  # 受け取ったギフト数
    total_points_received = db.Column(db.Integer, default=0)  # 受け取った総ポイント
    total_earnings = db.Column(db.Integer, default=0)  # 総収益（円）
    
    # ギフト目標（進捗メーター用）
    monthly_gift_goal = db.Column(db.Integer, default=0)  # 今月のギフト目標（ポイント）
    monthly_gift_goal_message = db.Column(db.String(200))  # 目標メッセージ（例: 「目標達成で○○します！」）
    show_gift_progress = db.Column(db.Boolean, default=False)  # 進捗メーターを公開するか
    
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーション
    shop = db.relationship('Shop', backref='casts')
    gift_transactions = db.relationship('GiftTransaction', backref='cast', lazy='dynamic')
    
    @property
    def name_display(self):
        """表示名（display_nameがあればそちら）"""
        return self.display_name or self.name
    
    @property
    def image_url(self):
        """画像URL (cloud, database, or local)"""
        if self.image_filename:
            # Cloudinary public_id形式
            if self.image_filename.startswith('night-walk/') or self.image_filename.startswith('http'):
                if self.image_filename.startswith('http'):
                    return self.image_filename
                from flask import current_app
                cloud_name = current_app.config.get('CLOUDINARY_CLOUD_NAME')
                if cloud_name:
                    return f"https://res.cloudinary.com/{cloud_name}/image/upload/{self.image_filename}"
            # DB保存形式 (folder/file.ext) → /images_db/ ルートで配信
            if '/' in self.image_filename:
                return f'/images_db/{self.image_filename}'
            return url_for('static', filename=f'uploads/casts/{self.image_filename}')
        return url_for('static', filename='images/default_cast.png')
    
    def add_gift(self, points, earnings):
        """ギフト受け取り時の集計更新"""
        self.total_gifts_received += 1
        self.total_points_received += points
        self.total_earnings += earnings
    
    @classmethod
    def get_active_by_shop(cls, shop_id):
        """店舗のアクティブなキャスト一覧"""
        return cls.query.filter_by(
            shop_id=shop_id,
            is_active=True
        ).order_by(cls.sort_order, cls.name).all()
    
    @property
    def area(self):
        """キャストのエリア（店舗経由で取得）"""
        if self.shop:
            return self.shop.area
        return None
    
    @property
    def area_key(self):
        """エリアキー（ランキング用）"""
        # 店舗のarea（岡山、倉敷など）からエリアキーを取得
        area = self.area
        if area in ['岡山', '倉敷']:
            return 'okayama'  # 岡山県として集計
        return 'okayama'  # デフォルト
    
    @property
    def active_badges(self):
        """現在有効なバッジ"""
        from .ranking import CastBadgeHistory
        return CastBadgeHistory.get_active_badges(self.id)
    
    @property
    def is_top1(self):
        """現在TOP1かどうか"""
        badges = self.active_badges
        return any(b.badge_type == 'area_top1' for b in badges)
    
    @property
    def best_badge(self):
        """現在の最高ランクバッジ"""
        badges = self.active_badges
        if not badges:
            return None
        # TOP1 > TOP3 > TOP10の順で返す
        for badge_type in ['area_top1', 'area_top3', 'area_top10']:
            for badge in badges:
                if badge.badge_type == badge_type:
                    return badge
        return badges[0] if badges else None
    
    @property
    def current_rank(self):
        """現在月のランキング順位"""
        from datetime import date
        from .ranking import CastMonthlyRanking
        today = date.today()
        ranking = CastMonthlyRanking.query.filter_by(
            cast_id=self.id,
            area=self.area_key,
            year=today.year,
            month=today.month,
            is_finalized=True
        ).first()
        return ranking.rank if ranking else None
    
    # ==================== ギフト進捗メーター ====================
    
    @property
    def monthly_gift_received(self):
        """今月受け取ったギフトポイント合計"""
        from datetime import date
        from sqlalchemy import func
        
        today = date.today()
        first_day = date(today.year, today.month, 1)
        
        result = db.session.query(
            func.sum(GiftTransaction.points_used)
        ).filter(
            GiftTransaction.cast_id == self.id,
            GiftTransaction.status == GiftTransaction.STATUS_COMPLETED,
            func.date(GiftTransaction.created_at) >= first_day
        ).scalar()
        
        return result or 0
    
    @property
    def gift_progress_percent(self):
        """ギフト目標達成率（%）"""
        if not self.monthly_gift_goal or self.monthly_gift_goal <= 0:
            return 0
        
        received = self.monthly_gift_received
        percent = (received / self.monthly_gift_goal) * 100
        return min(100, round(percent, 1))  # 100%を上限
    
    @property
    def gift_progress_remaining(self):
        """目標達成までの残りポイント"""
        if not self.monthly_gift_goal or self.monthly_gift_goal <= 0:
            return 0
        
        remaining = self.monthly_gift_goal - self.monthly_gift_received
        return max(0, remaining)
    
    @property
    def is_gift_goal_achieved(self):
        """目標達成したか"""
        return self.gift_progress_percent >= 100
    
    def set_monthly_goal(self, goal_points, message=None, show_progress=True):
        """月次ギフト目標を設定"""
        self.monthly_gift_goal = goal_points
        self.monthly_gift_goal_message = message
        self.show_gift_progress = show_progress
        self.updated_at = datetime.utcnow()
    
    # ==================== キャストログイン機能 ====================
    
    def generate_login_code(self):
        """8桁のログインコードを生成"""
        while True:
            code = ''.join(secrets.choice('0123456789') for _ in range(8))
            # 重複チェック
            existing = Cast.query.filter_by(login_code=code).first()
            if not existing:
                self.login_code = code
                return code
    
    def set_pin(self, pin):
        """4桁PINを設定（ハッシュ化して保存）"""
        if len(pin) != 4 or not pin.isdigit():
            raise ValueError("PINは4桁の数字である必要があります")
        self.pin_hash = generate_password_hash(pin)
    
    def check_pin(self, pin):
        """PINを検証"""
        if not self.pin_hash:
            return False
        return check_password_hash(self.pin_hash, pin)
    
    def record_login(self):
        """ログイン日時を記録"""
        self.last_login_at = datetime.utcnow()
    
    @property
    def has_login_enabled(self):
        """ログインが有効か"""
        return bool(self.login_code and self.pin_hash)
    
    @property
    def work_status_label(self):
        """出勤状況ラベル"""
        labels = {
            self.WORK_STATUS_OFF: '休み',
            self.WORK_STATUS_WORKING: '出勤中',
            self.WORK_STATUS_SCHEDULED: '出勤予定'
        }
        return labels.get(self.work_status, '不明')
    
    @property
    def work_status_color(self):
        """出勤状況の色"""
        colors = {
            self.WORK_STATUS_OFF: 'secondary',
            self.WORK_STATUS_WORKING: 'success',
            self.WORK_STATUS_SCHEDULED: 'warning'
        }
        return colors.get(self.work_status, 'secondary')
    
    @property
    def work_time_display(self):
        """出勤時間の表示"""
        if self.work_status == self.WORK_STATUS_OFF:
            return None
        if self.work_start_time and self.work_end_time:
            return f"{self.work_start_time}〜{self.work_end_time}"
        elif self.work_start_time:
            return f"{self.work_start_time}〜"
        return None
    
    def __repr__(self):
        return f'<Cast {self.name_display}>'


class Gift(db.Model):
    """ギフト定義"""
    __tablename__ = 'gifts'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255))
    points = db.Column(db.Integer, nullable=False)  # 必要ポイント
    image_filename = db.Column(db.String(255))
    
    # 分配率（%）- 合計100%
    # 要件: キャスト40% / 店舗30% / 運営30%
    cast_rate = db.Column(db.Integer, default=40)      # キャスト: 40%
    shop_rate = db.Column(db.Integer, default=30)      # 店舗: 30%
    platform_rate = db.Column(db.Integer, default=30)  # 運営: 30%
    
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def cast_amount(self):
        """キャスト取り分（円）"""
        return int(self.points * self.cast_rate / 100)
    
    @property
    def shop_amount(self):
        """店舗取り分（円）"""
        return int(self.points * self.shop_rate / 100)
    
    @property
    def platform_amount(self):
        """運営取り分（円）"""
        return int(self.points * self.platform_rate / 100)
    
    @property
    def image_url(self):
        """画像URL (cloud, database, or local)"""
        if self.image_filename:
            # Cloudinary public_id形式
            if self.image_filename.startswith('night-walk/') or self.image_filename.startswith('http'):
                if self.image_filename.startswith('http'):
                    return self.image_filename
                from flask import current_app
                cloud_name = current_app.config.get('CLOUDINARY_CLOUD_NAME')
                if cloud_name:
                    return f"https://res.cloudinary.com/{cloud_name}/image/upload/{self.image_filename}"
            # DB保存形式 (folder/file.ext) → /images_db/ ルートで配信
            if '/' in self.image_filename:
                return f'/images_db/{self.image_filename}'
            return url_for('static', filename=f'uploads/gifts/{self.image_filename}')
        return url_for('static', filename='images/default_gift.png')
    
    @classmethod
    def get_active_gifts(cls):
        """有効なギフト一覧"""
        return cls.query.filter_by(is_active=True).order_by(cls.sort_order, cls.points).all()
    
    def __repr__(self):
        return f'<Gift {self.name} {self.points}pt>'


class GiftTransaction(db.Model):
    """ギフト送信履歴"""
    __tablename__ = 'gift_transactions'
    
    STATUS_COMPLETED = 'completed'  # 完了
    STATUS_REFUNDED = 'refunded'    # 返金済み
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id', ondelete='CASCADE'), nullable=False, index=True)
    cast_id = db.Column(db.Integer, db.ForeignKey('casts.id', ondelete='CASCADE'), nullable=False, index=True)
    gift_id = db.Column(db.Integer, db.ForeignKey('gifts.id', ondelete='CASCADE'), nullable=False)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)
    
    points_used = db.Column(db.Integer, nullable=False)
    message = db.Column(db.String(200))  # 応援メッセージ
    
    # 分配金額（円）
    cast_amount = db.Column(db.Integer, nullable=False)
    shop_amount = db.Column(db.Integer, nullable=False)
    platform_amount = db.Column(db.Integer, nullable=False)
    
    status = db.Column(db.String(20), default=STATUS_COMPLETED)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーション
    gift = db.relationship('Gift')
    shop = db.relationship('Shop')
    
    @property
    def total_amount(self):
        """合計金額"""
        return self.cast_amount + self.shop_amount + self.platform_amount
    
    def __repr__(self):
        return f'<GiftTransaction {self.id} {self.points_used}pt>'
