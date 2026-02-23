"""
Night-Walk MVP - Booking/Call Models (Twilio)
直前限定予約システム対応
"""
from datetime import datetime, timedelta
from ..extensions import db


class Call(db.Model):
    """Twilio call log model."""
    __tablename__ = 'calls'
    
    # Call statuses
    STATUS_INITIATED = 'initiated'
    STATUS_RINGING = 'ringing'
    STATUS_ANSWERED = 'answered'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_NO_ANSWER = 'no-answer'
    STATUS_BUSY = 'busy'
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)
    call_sid = db.Column(db.String(100), unique=True, index=True)  # Twilio Call SID
    caller_number = db.Column(db.String(20))
    status = db.Column(db.String(30))
    duration = db.Column(db.Integer)  # 通話秒数
    digits_pressed = db.Column(db.String(10))  # プッシュ番号
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    ended_at = db.Column(db.DateTime)
    
    # Relationships
    shop = db.relationship('Shop', back_populates='calls')
    booking_log = db.relationship('BookingLog', back_populates='call', uselist=False)
    
    @property
    def is_successful(self):
        """Check if call was successful."""
        return self.status == self.STATUS_COMPLETED
    
    def __repr__(self):
        return f'<Call {self.call_sid} shop={self.shop_id}>'


class BookingLog(db.Model):
    """
    Booking log model - records reservation attempts.
    直前限定予約（30〜60分前）＋指名キャスト必須対応
    """
    __tablename__ = 'booking_logs'
    
    # Booking types
    TYPE_PHONE = 'phone'
    TYPE_WEB = 'web'  # Web予約
    
    # Booking statuses (拡張)
    STATUS_PENDING = 'pending'        # 予約待機中（来店待ち）
    STATUS_CONFIRMED = 'confirmed'    # 予約確定
    STATUS_COMPLETED = 'completed'    # 来店完了
    STATUS_CANCELLED = 'cancelled'    # キャンセル（ユーザー都合）
    STATUS_NO_SHOW = 'no_show'        # 遅刻キャンセル（10分超過）
    STATUS_NO_ANSWER = 'no_answer'    # 電話応答なし
    STATUS_FAILED = 'failed'          # 予約失敗
    
    STATUS_LABELS = {
        STATUS_PENDING: '来店待ち',
        STATUS_CONFIRMED: '予約確定',
        STATUS_COMPLETED: '来店完了',
        STATUS_CANCELLED: 'キャンセル',
        STATUS_NO_SHOW: '遅刻キャンセル',
        STATUS_NO_ANSWER: '応答なし',
        STATUS_FAILED: '予約失敗',
    }
    
    # 予約時間の制限（分）
    MIN_ADVANCE_MINUTES = 15  # 最低15分前
    MAX_ADVANCE_MINUTES = 60  # 最大60分前
    LATE_CANCEL_MINUTES = 10  # 10分遅刻でキャンセル
    
    id = db.Column(db.Integer, primary_key=True)
    call_id = db.Column(db.Integer, db.ForeignKey('calls.id', ondelete='SET NULL'), index=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # 指名キャスト（NULLの場合はフリー指名なし）
    cast_id = db.Column(db.Integer, db.ForeignKey('casts.id', ondelete='SET NULL'), index=True)
    is_free_nomination = db.Column(db.Boolean, default=False)
    
    # 顧客情報
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id', ondelete='SET NULL'), index=True)
    customer_phone = db.Column(db.String(20))  # 予約時の電話番号
    customer_name = db.Column(db.String(100))  # 予約者名
    party_size = db.Column(db.Integer, default=1)  # 人数
    
    # 予約時間（直前限定：30〜60分後）
    scheduled_at = db.Column(db.DateTime, index=True)  # 予約（来店予定）時刻
    
    booking_type = db.Column(db.String(20), nullable=False, default=TYPE_WEB)
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING, index=True)
    notes = db.Column(db.Text)
    
    # キャンセル情報
    cancelled_at = db.Column(db.DateTime)
    cancel_reason = db.Column(db.String(255))
    
    # 来店確認
    checked_in_at = db.Column(db.DateTime)  # 来店確認時刻
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    call = db.relationship('Call', back_populates='booking_log')
    shop = db.relationship('Shop', back_populates='booking_logs')
    cast = db.relationship('Cast', backref=db.backref('bookings', lazy='dynamic'))
    customer = db.relationship('Customer', backref=db.backref('bookings', lazy='dynamic'))
    
    @property
    def status_label(self):
        """ステータスの日本語ラベル"""
        return self.STATUS_LABELS.get(self.status, self.status)
    
    @property
    def is_late(self):
        """遅刻判定（予約時刻から10分超過）"""
        if not self.scheduled_at:
            return False
        now = datetime.utcnow()
        late_threshold = self.scheduled_at + timedelta(minutes=self.LATE_CANCEL_MINUTES)
        return now > late_threshold
    
    @property
    def minutes_until_scheduled(self):
        """予約時刻までの残り分数"""
        if not self.scheduled_at:
            return None
        now = datetime.utcnow()
        delta = self.scheduled_at - now
        return int(delta.total_seconds() / 60)
    
    @property
    def can_cancel(self):
        """キャンセル可能か"""
        return self.status in [self.STATUS_PENDING, self.STATUS_CONFIRMED]
    
    @classmethod
    def validate_scheduled_time(cls, scheduled_at):
        """
        予約時刻のバリデーション（30〜60分後のみ）
        
        Returns:
            tuple: (is_valid: bool, error_message: str or None)
        """
        if not scheduled_at:
            return False, '予約時刻を指定してください'
        
        now = datetime.utcnow()
        delta_minutes = (scheduled_at - now).total_seconds() / 60
        
        if delta_minutes < cls.MIN_ADVANCE_MINUTES:
            return False, f'予約は{cls.MIN_ADVANCE_MINUTES}分以上先の時刻を指定してください'
        
        if delta_minutes > cls.MAX_ADVANCE_MINUTES:
            return False, f'予約は{cls.MAX_ADVANCE_MINUTES}分以内の時刻のみ指定できます（直前限定予約）'
        
        return True, None
    
    @classmethod
    def get_available_times(cls):
        """
        選択可能な予約時刻リストを取得（30〜60分後、5分刻み）
        
        Returns:
            list: datetime objects
        """
        now = datetime.utcnow()
        times = []
        
        # 30分後から60分後まで5分刻み
        for minutes in range(cls.MIN_ADVANCE_MINUTES, cls.MAX_ADVANCE_MINUTES + 1, 5):
            time = now + timedelta(minutes=minutes)
            # 分を5分単位に丸める
            time = time.replace(minute=(time.minute // 5) * 5, second=0, microsecond=0)
            if time not in times:
                times.append(time)
        
        return times
    
    def confirm(self):
        """予約を確定"""
        self.status = self.STATUS_CONFIRMED
        self.updated_at = datetime.utcnow()
    
    def complete(self):
        """来店完了"""
        self.status = self.STATUS_COMPLETED
        self.checked_in_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def cancel(self, reason=None):
        """キャンセル"""
        self.status = self.STATUS_CANCELLED
        self.cancelled_at = datetime.utcnow()
        self.cancel_reason = reason
        self.updated_at = datetime.utcnow()
    
    def mark_no_show(self):
        """遅刻キャンセル（10分超過）"""
        self.status = self.STATUS_NO_SHOW
        self.cancelled_at = datetime.utcnow()
        self.cancel_reason = f'{self.LATE_CANCEL_MINUTES}分遅刻による自動キャンセル'
        self.updated_at = datetime.utcnow()
    
    @classmethod
    def get_pending_bookings(cls, shop_id=None):
        """来店待ちの予約を取得"""
        query = cls.query.filter(
            cls.status.in_([cls.STATUS_PENDING, cls.STATUS_CONFIRMED])
        )
        if shop_id:
            query = query.filter(cls.shop_id == shop_id)
        return query.order_by(cls.scheduled_at).all()
    
    @classmethod
    def get_late_bookings(cls):
        """
        遅刻判定対象の予約を取得（予約時刻から10分超過、まだキャンセルされていない）
        自動キャンセルジョブ用
        """
        now = datetime.utcnow()
        threshold = now - timedelta(minutes=cls.LATE_CANCEL_MINUTES)
        
        return cls.query.filter(
            cls.status.in_([cls.STATUS_PENDING, cls.STATUS_CONFIRMED]),
            cls.scheduled_at != None,
            cls.scheduled_at < threshold
        ).all()
    
    def __repr__(self):
        return f'<BookingLog shop={self.shop_id} cast={self.cast_id} status={self.status}>'
