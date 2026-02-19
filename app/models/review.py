# app/models/review.py
"""店舗口コミ・評価モデル"""

from datetime import datetime, timedelta
from ..extensions import db


class ShopReview(db.Model):
    """店舗口コミ評価（星1〜5のタップ評価のみ）"""
    __tablename__ = 'shop_reviews'
    
    # 評価値
    MIN_RATING = 1
    MAX_RATING = 5
    
    # ステータス
    STATUS_PENDING = 'pending'      # SMS認証待ち
    STATUS_VERIFIED = 'verified'    # 認証済み・有効
    STATUS_REJECTED = 'rejected'    # 不正判定で却下
    
    STATUSES = [STATUS_PENDING, STATUS_VERIFIED, STATUS_REJECTED]
    
    STATUS_LABELS = {
        STATUS_PENDING: '認証待ち',
        STATUS_VERIFIED: '有効',
        STATUS_REJECTED: '却下',
    }
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id', ondelete='SET NULL'), index=True)
    
    # 評価（星1〜5のみ、文字入力不可）
    rating = db.Column(db.Integer, nullable=False)
    
    # 認証情報
    phone_number = db.Column(db.String(20), nullable=False, index=True)  # SMS認証用
    device_fingerprint = db.Column(db.String(64), index=True)  # 端末識別（1端末1評価）
    
    # ステータス
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING, index=True)
    verified_at = db.Column(db.DateTime)  # SMS認証完了日時
    
    # ポイント還元
    points_rewarded = db.Column(db.Integer, default=0)  # 付与されたポイント
    points_rewarded_at = db.Column(db.DateTime)
    
    # メタ情報
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーション
    shop = db.relationship('Shop', backref=db.backref('reviews', lazy='dynamic'))
    customer = db.relationship('Customer', backref=db.backref('shop_reviews', lazy='dynamic'))
    
    # インデックス
    __table_args__ = (
        db.UniqueConstraint('shop_id', 'phone_number', name='uq_shop_review_phone'),
        db.UniqueConstraint('shop_id', 'device_fingerprint', name='uq_shop_review_device'),
        db.Index('ix_review_shop_status', 'shop_id', 'status'),
        db.Index('ix_review_created', 'created_at'),
    )
    
    # 口コミ投稿ポイント還元 → 廃止（新規会員登録ボーナスに一本化）
    REWARD_POINTS = 0
    
    @property
    def status_label(self):
        """ステータス表示名"""
        return self.STATUS_LABELS.get(self.status, self.status)
    
    @property
    def is_verified(self):
        """認証済みかどうか"""
        return self.status == self.STATUS_VERIFIED
    
    @classmethod
    def can_review(cls, shop_id, phone_number=None, device_fingerprint=None):
        """
        口コミ投稿可能かチェック
        - 同一電話番号からの重複投稿禁止
        - 同一端末からの重複投稿禁止
        
        Returns:
            tuple: (can_review: bool, reason: str or None)
        """
        # 電話番号チェック
        if phone_number:
            existing_phone = cls.query.filter(
                cls.shop_id == shop_id,
                cls.phone_number == phone_number,
                cls.status != cls.STATUS_REJECTED
            ).first()
            if existing_phone:
                return False, 'この電話番号では既に評価済みです'
        
        # 端末チェック
        if device_fingerprint:
            existing_device = cls.query.filter(
                cls.shop_id == shop_id,
                cls.device_fingerprint == device_fingerprint,
                cls.status != cls.STATUS_REJECTED
            ).first()
            if existing_device:
                return False, 'この端末では既に評価済みです'
        
        return True, None
    
    @classmethod
    def create_review(cls, shop_id, rating, phone_number, customer_id=None,
                      device_fingerprint=None, ip_address=None, user_agent=None):
        """
        口コミを作成（SMS認証待ち状態で作成）
        
        Returns:
            tuple: (review: ShopReview or None, error: str or None)
        """
        # バリデーション
        if not (cls.MIN_RATING <= rating <= cls.MAX_RATING):
            return None, f'評価は{cls.MIN_RATING}〜{cls.MAX_RATING}で入力してください'
        
        # 重複チェック
        can_review, reason = cls.can_review(shop_id, phone_number, device_fingerprint)
        if not can_review:
            return None, reason
        
        review = cls(
            shop_id=shop_id,
            customer_id=customer_id,
            rating=rating,
            phone_number=phone_number,
            device_fingerprint=device_fingerprint,
            ip_address=ip_address,
            user_agent=user_agent[:255] if user_agent else None,
            status=cls.STATUS_PENDING
        )
        
        db.session.add(review)
        return review, None
    
    def verify(self):
        """SMS認証完了"""
        if self.status != self.STATUS_PENDING:
            return False
        
        self.status = self.STATUS_VERIFIED
        self.verified_at = datetime.utcnow()
        return True
    
    def reward_points(self, customer):
        """ポイント還元 → 廃止（互換性のため残すが常にFalse）"""
        return False
    
    def reject(self, reason=None):
        """不正として却下"""
        self.status = self.STATUS_REJECTED
    
    @classmethod
    def get_shop_rating(cls, shop_id):
        """
        店舗の平均評価を取得
        
        Returns:
            dict: {'average': float, 'count': int, 'distribution': dict}
        """
        verified_reviews = cls.query.filter(
            cls.shop_id == shop_id,
            cls.status == cls.STATUS_VERIFIED
        )
        
        count = verified_reviews.count()
        if count == 0:
            return {
                'average': 0,
                'count': 0,
                'distribution': {i: 0 for i in range(1, 6)}
            }
        
        # 平均計算
        total = db.session.query(
            db.func.sum(cls.rating)
        ).filter(
            cls.shop_id == shop_id,
            cls.status == cls.STATUS_VERIFIED
        ).scalar() or 0
        
        average = total / count
        
        # 分布計算
        distribution = {}
        for i in range(1, 6):
            distribution[i] = verified_reviews.filter(cls.rating == i).count()
        
        return {
            'average': round(average, 1),
            'count': count,
            'distribution': distribution
        }
    
    @classmethod
    def get_recent_reviews(cls, shop_id, limit=10):
        """最近の口コミを取得"""
        return cls.query.filter(
            cls.shop_id == shop_id,
            cls.status == cls.STATUS_VERIFIED
        ).order_by(cls.created_at.desc()).limit(limit).all()
    
    def __repr__(self):
        return f'<ShopReview shop={self.shop_id} rating={self.rating}>'


class PhoneVerification(db.Model):
    """SMS認証管理"""
    __tablename__ = 'phone_verifications'
    
    # ステータス
    STATUS_PENDING = 'pending'
    STATUS_VERIFIED = 'verified'
    STATUS_EXPIRED = 'expired'
    STATUS_FAILED = 'failed'  # 認証失敗（回数超過）
    
    # 認証コード有効期限（分）
    CODE_EXPIRY_MINUTES = 10
    
    # 最大試行回数
    MAX_ATTEMPTS = 3
    
    # 同一電話番号からの1日あたりの送信上限
    DAILY_LIMIT = 5
    
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), nullable=False, index=True)
    verification_code = db.Column(db.String(6), nullable=False)  # 6桁の認証コード
    
    # 認証対象
    purpose = db.Column(db.String(50), nullable=False, index=True)  # 'review', 'signup' など
    target_id = db.Column(db.Integer)  # review_id など
    
    # ステータス
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING, index=True)
    attempts = db.Column(db.Integer, default=0)  # 試行回数
    
    # 有効期限
    expires_at = db.Column(db.DateTime, nullable=False)
    verified_at = db.Column(db.DateTime)
    
    # メタ情報
    ip_address = db.Column(db.String(45))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.Index('ix_phone_verification_lookup', 'phone_number', 'status', 'expires_at'),
    )
    
    @classmethod
    def generate_code(cls):
        """6桁のランダム認証コードを生成"""
        import random
        return str(random.randint(100000, 999999))
    
    @classmethod
    def can_send(cls, phone_number):
        """
        SMS送信可能かチェック（1日あたりの上限）
        
        Returns:
            tuple: (can_send: bool, reason: str or None)
        """
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        daily_count = cls.query.filter(
            cls.phone_number == phone_number,
            cls.created_at >= today_start
        ).count()
        
        if daily_count >= cls.DAILY_LIMIT:
            return False, '本日の認証コード送信上限に達しました。明日以降にお試しください。'
        
        return True, None
    
    @classmethod
    def create_verification(cls, phone_number, purpose, target_id=None, ip_address=None):
        """
        認証レコードを作成
        
        Returns:
            tuple: (verification: PhoneVerification or None, error: str or None)
        """
        # 送信可能かチェック
        can_send, reason = cls.can_send(phone_number)
        if not can_send:
            return None, reason
        
        # 既存のPending状態を無効化
        cls.query.filter(
            cls.phone_number == phone_number,
            cls.purpose == purpose,
            cls.status == cls.STATUS_PENDING
        ).update({'status': cls.STATUS_EXPIRED})
        
        verification = cls(
            phone_number=phone_number,
            verification_code=cls.generate_code(),
            purpose=purpose,
            target_id=target_id,
            ip_address=ip_address,
            expires_at=datetime.utcnow() + timedelta(minutes=cls.CODE_EXPIRY_MINUTES)
        )
        
        db.session.add(verification)
        return verification, None
    
    @property
    def is_expired(self):
        """有効期限切れかどうか"""
        return datetime.utcnow() > self.expires_at
    
    def verify(self, code):
        """
        認証コードを検証
        
        Returns:
            tuple: (success: bool, error: str or None)
        """
        if self.status != self.STATUS_PENDING:
            return False, '認証コードは既に使用されています'
        
        if self.is_expired:
            self.status = self.STATUS_EXPIRED
            return False, '認証コードの有効期限が切れています'
        
        self.attempts += 1
        
        if self.verification_code != code:
            if self.attempts >= self.MAX_ATTEMPTS:
                self.status = self.STATUS_FAILED
                return False, '認証コードの入力回数が上限に達しました'
            
            remaining = self.MAX_ATTEMPTS - self.attempts
            return False, f'認証コードが正しくありません（残り{remaining}回）'
        
        # 認証成功
        self.status = self.STATUS_VERIFIED
        self.verified_at = datetime.utcnow()
        
        return True, None
    
    @classmethod
    def get_pending(cls, phone_number, purpose):
        """有効なPending状態の認証を取得"""
        return cls.query.filter(
            cls.phone_number == phone_number,
            cls.purpose == purpose,
            cls.status == cls.STATUS_PENDING,
            cls.expires_at > datetime.utcnow()
        ).order_by(cls.created_at.desc()).first()
    
    def __repr__(self):
        return f'<PhoneVerification {self.phone_number} {self.purpose}>'


class ShopReviewScore(db.Model):
    """店舗口コミスコア集計（月次キャッシュ）"""
    __tablename__ = 'shop_review_scores'
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)
    area = db.Column(db.String(50), nullable=False, index=True)
    
    # 集計期間
    year = db.Column(db.Integer, nullable=False, index=True)
    month = db.Column(db.Integer, nullable=False, index=True)
    
    # 評価集計
    review_count = db.Column(db.Integer, default=0)      # 口コミ数
    rating_sum = db.Column(db.Integer, default=0)        # 評価合計
    average_rating = db.Column(db.Float, default=0)      # 平均評価
    
    # スコア（ランキング用）
    review_score = db.Column(db.Float, default=0)        # 口コミスコア
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーション
    shop = db.relationship('Shop', backref=db.backref('review_scores', lazy='dynamic'))
    
    __table_args__ = (
        db.UniqueConstraint('shop_id', 'year', 'month', name='uq_shop_review_score_period'),
        db.Index('ix_shop_review_score_period', 'year', 'month', 'area', 'review_score'),
    )
    
    @classmethod
    def calculate_for_shop(cls, shop_id, year, month):
        """店舗の月次口コミスコアを計算"""
        from .shop import Shop
        
        shop = Shop.query.get(shop_id)
        if not shop:
            return None
        
        # 期間内の認証済み口コミを集計
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        reviews = ShopReview.query.filter(
            ShopReview.shop_id == shop_id,
            ShopReview.status == ShopReview.STATUS_VERIFIED,
            ShopReview.verified_at >= start_date,
            ShopReview.verified_at < end_date
        )
        
        count = reviews.count()
        rating_sum = db.session.query(
            db.func.sum(ShopReview.rating)
        ).filter(
            ShopReview.shop_id == shop_id,
            ShopReview.status == ShopReview.STATUS_VERIFIED,
            ShopReview.verified_at >= start_date,
            ShopReview.verified_at < end_date
        ).scalar() or 0
        
        average = rating_sum / count if count > 0 else 0
        
        # スコア計算: 口コミ数 × 平均評価（重み付け）
        # 口コミが多く、評価が高いほど高スコア
        review_score = count * average * 10  # 係数調整
        
        # 既存レコードを更新または新規作成
        score = cls.query.filter_by(
            shop_id=shop_id,
            year=year,
            month=month
        ).first()
        
        if not score:
            score = cls(
                shop_id=shop_id,
                area=shop.area,
                year=year,
                month=month
            )
            db.session.add(score)
        
        score.review_count = count
        score.rating_sum = rating_sum
        score.average_rating = round(average, 2)
        score.review_score = round(review_score, 2)
        
        return score
    
    def __repr__(self):
        return f'<ShopReviewScore shop={self.shop_id} {self.year}/{self.month}>'
