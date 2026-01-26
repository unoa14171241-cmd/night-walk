"""
Night-Walk MVP - Commission Models (送客手数料)
"""
from datetime import datetime, date
from ..extensions import db


# カテゴリ別デフォルト送客手数料（円）
DEFAULT_COMMISSION_BY_CATEGORY = {
    'snack': 700,       # スナック
    'concafe': 700,     # コンカフェ
    'kyabakura': 1800,  # キャバクラ
    'fuzoku': 2000,     # 風俗
    'deriheru': 2000,   # デリヘル
    'lounge': 1000,     # ラウンジ
    'club': 1000,       # クラブ
    'bar': 700,         # バー
    'other': 1000,      # その他
}


def get_default_commission(category):
    """
    カテゴリからデフォルト送客手数料を取得する。
    Args:
        category: 店舗カテゴリ
    Returns:
        int: デフォルト手数料（円）
    """
    return DEFAULT_COMMISSION_BY_CATEGORY.get(category, 1000)


class CommissionRate(db.Model):
    """Commission rate settings per shop (店舗ごとの手数料設定)."""
    __tablename__ = 'commission_rates'
    
    # Commission types
    TYPE_FIXED = 'fixed'           # 固定額（1件あたり）
    TYPE_PERCENTAGE = 'percentage' # パーセンテージ（売上に対して）
    
    TYPE_LABELS = {
        TYPE_FIXED: '固定額',
        TYPE_PERCENTAGE: 'パーセンテージ',
    }
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)
    commission_type = db.Column(db.String(20), nullable=False, default=TYPE_FIXED)
    fixed_amount = db.Column(db.Integer, default=1000)       # 固定額（円）
    percentage_rate = db.Column(db.Float, default=10.0)      # パーセンテージ（%）
    min_amount = db.Column(db.Integer, default=0)            # 最低手数料
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    shop = db.relationship('Shop', backref=db.backref('commission_rate', uselist=False))
    
    def calculate(self, base_amount=None, guest_count=1):
        """
        Calculate commission amount.
        Args:
            base_amount: 売上金額（percentage typeの場合に必要）
            guest_count: 来店人数
        Returns:
            int: 手数料金額（円）
        """
        if self.commission_type == self.TYPE_FIXED:
            return self.fixed_amount * guest_count
        elif self.commission_type == self.TYPE_PERCENTAGE and base_amount:
            amount = int(base_amount * (self.percentage_rate / 100))
            return max(amount, self.min_amount)
        return (self.min_amount or self.fixed_amount) * guest_count
    
    @property
    def type_label(self):
        return self.TYPE_LABELS.get(self.commission_type, self.commission_type)
    
    @property
    def rate_display(self):
        """Display-friendly rate string."""
        if self.commission_type == self.TYPE_FIXED:
            return f'¥{self.fixed_amount:,}/件'
        else:
            return f'{self.percentage_rate}%'
    
    def __repr__(self):
        return f'<CommissionRate shop={self.shop_id} {self.rate_display}>'


class Commission(db.Model):
    """Individual commission record (送客手数料明細)."""
    __tablename__ = 'commissions'
    
    # Status
    STATUS_PENDING = 'pending'       # 確定待ち
    STATUS_CONFIRMED = 'confirmed'   # 確定済み
    STATUS_CANCELLED = 'cancelled'   # キャンセル
    STATUS_PAID = 'paid'             # 支払済み
    
    STATUS_LABELS = {
        STATUS_PENDING: '確定待ち',
        STATUS_CONFIRMED: '確定済み',
        STATUS_CANCELLED: 'キャンセル',
        STATUS_PAID: '支払済み',
    }
    
    # Source types
    SOURCE_PHONE = 'phone'           # 電話予約
    SOURCE_WEB = 'web'               # Web予約
    SOURCE_WALK_IN = 'walk_in'       # 来店（手動入力）
    
    SOURCE_LABELS = {
        SOURCE_PHONE: '電話予約',
        SOURCE_WEB: 'Web予約',
        SOURCE_WALK_IN: '来店',
    }
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=False, index=True)
    booking_log_id = db.Column(db.Integer, db.ForeignKey('booking_logs.id'), index=True)  # 関連予約
    monthly_billing_id = db.Column(db.Integer, db.ForeignKey('monthly_billings.id'), index=True)  # 月次請求
    
    # Commission details
    source = db.Column(db.String(20), nullable=False, default=SOURCE_PHONE)
    guest_count = db.Column(db.Integer, default=1)           # 来店人数
    sales_amount = db.Column(db.Integer)                     # 売上金額（把握している場合）
    commission_amount = db.Column(db.Integer, nullable=False) # 手数料金額
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING, index=True)
    
    # Additional info
    visit_date = db.Column(db.Date, nullable=False, index=True)  # 来店日
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    confirmed_at = db.Column(db.DateTime)  # 確定日時
    
    # Relationships
    shop = db.relationship('Shop', backref=db.backref('commissions', lazy='dynamic'))
    booking_log = db.relationship('BookingLog', backref='commission')
    monthly_billing = db.relationship('MonthlyBilling', back_populates='commissions')
    
    @property
    def status_label(self):
        return self.STATUS_LABELS.get(self.status, self.status)
    
    @property
    def source_label(self):
        return self.SOURCE_LABELS.get(self.source, self.source)
    
    def confirm(self):
        """Confirm this commission."""
        self.status = self.STATUS_CONFIRMED
        self.confirmed_at = datetime.utcnow()
    
    def cancel(self):
        """Cancel this commission."""
        self.status = self.STATUS_CANCELLED
    
    @classmethod
    def create_from_booking(cls, booking_log, visit_date=None, guest_count=1):
        """
        Create commission from booking log.
        """
        shop = booking_log.shop
        rate = CommissionRate.query.filter_by(shop_id=shop.id, is_active=True).first()
        
        if rate:
            commission_amount = rate.calculate(guest_count=guest_count)
        else:
            # カスタム設定がない場合はカテゴリ別デフォルト手数料を使用
            default_rate = get_default_commission(shop.category)
            commission_amount = default_rate * guest_count
        
        commission = cls(
            shop_id=shop.id,
            booking_log_id=booking_log.id,
            source=cls.SOURCE_PHONE,
            visit_date=visit_date or date.today(),
            guest_count=guest_count,
            commission_amount=commission_amount,
            status=cls.STATUS_PENDING
        )
        
        # Link to monthly billing
        billing = MonthlyBilling.get_or_create(shop.id, commission.visit_date.year, commission.visit_date.month)
        commission.monthly_billing = billing
        
        return commission
    
    def __repr__(self):
        return f'<Commission shop={self.shop_id} amount={self.commission_amount} status={self.status}>'


class MonthlyBilling(db.Model):
    """Monthly billing summary (月次請求)."""
    __tablename__ = 'monthly_billings'
    
    # Status
    STATUS_OPEN = 'open'             # 集計中
    STATUS_CLOSED = 'closed'         # 締め済み
    STATUS_INVOICED = 'invoiced'     # 請求済み
    STATUS_PAID = 'paid'             # 支払済み
    STATUS_OVERDUE = 'overdue'       # 支払遅延
    
    STATUS_LABELS = {
        STATUS_OPEN: '集計中',
        STATUS_CLOSED: '締め済み',
        STATUS_INVOICED: '請求済み',
        STATUS_PAID: '支払済み',
        STATUS_OVERDUE: '支払遅延',
    }
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=False, index=True)
    
    # Billing period
    year = db.Column(db.Integer, nullable=False, index=True)
    month = db.Column(db.Integer, nullable=False, index=True)
    
    # Amounts
    total_commissions = db.Column(db.Integer, default=0)      # 送客件数
    subtotal = db.Column(db.Integer, default=0)               # 小計
    tax_amount = db.Column(db.Integer, default=0)             # 消費税
    total_amount = db.Column(db.Integer, default=0)           # 合計（税込）
    
    # Status & dates
    status = db.Column(db.String(20), nullable=False, default=STATUS_OPEN, index=True)
    closed_at = db.Column(db.DateTime)      # 締め日
    invoiced_at = db.Column(db.DateTime)    # 請求日
    due_date = db.Column(db.Date)           # 支払期限
    paid_at = db.Column(db.DateTime)        # 支払日
    
    # Invoice fields
    invoice_number = db.Column(db.String(50), unique=True, index=True)  # 請求書番号
    sent_at = db.Column(db.DateTime)        # 送付日時
    sent_to = db.Column(db.String(255))     # 送付先メールアドレス
    
    # Notes
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    shop = db.relationship('Shop', backref=db.backref('monthly_billings', lazy='dynamic'))
    commissions = db.relationship('Commission', back_populates='monthly_billing', lazy='dynamic')
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('shop_id', 'year', 'month', name='uq_monthly_billing_shop_period'),
    )
    
    @property
    def period_display(self):
        """Display-friendly period string."""
        return f'{self.year}年{self.month}月'
    
    @property
    def status_label(self):
        return self.STATUS_LABELS.get(self.status, self.status)
    
    def recalculate(self):
        """Recalculate totals from commissions."""
        confirmed = self.commissions.filter(
            Commission.status.in_([Commission.STATUS_CONFIRMED, Commission.STATUS_PAID])
        )
        self.total_commissions = confirmed.count()
        self.subtotal = sum(c.commission_amount for c in confirmed.all())
        self.tax_amount = int(self.subtotal * 0.10)  # 10%消費税
        self.total_amount = self.subtotal + self.tax_amount
    
    def close(self):
        """Close this billing period."""
        self.recalculate()
        self.status = self.STATUS_CLOSED
        self.closed_at = datetime.utcnow()
    
    def invoice(self, due_days=30):
        """Mark as invoiced."""
        from datetime import timedelta
        self.status = self.STATUS_INVOICED
        self.invoiced_at = datetime.utcnow()
        self.due_date = date.today() + timedelta(days=due_days)
    
    def mark_paid(self):
        """Mark as paid."""
        self.status = self.STATUS_PAID
        self.paid_at = datetime.utcnow()
        # Update all commissions
        for commission in self.commissions.filter_by(status=Commission.STATUS_CONFIRMED):
            commission.status = Commission.STATUS_PAID
    
    @classmethod
    def get_or_create(cls, shop_id, year, month):
        """Get existing or create new monthly billing."""
        billing = cls.query.filter_by(shop_id=shop_id, year=year, month=month).first()
        if not billing:
            billing = cls(shop_id=shop_id, year=year, month=month)
            db.session.add(billing)
        return billing
    
    def generate_invoice_number(self):
        """Generate unique invoice number."""
        # Format: NW-YYYYMM-SHOPID-SEQ
        seq = MonthlyBilling.query.filter(
            MonthlyBilling.year == self.year,
            MonthlyBilling.month == self.month,
            MonthlyBilling.invoice_number != None
        ).count() + 1
        self.invoice_number = f"NW-{self.year}{self.month:02d}-{self.shop_id:03d}-{seq:03d}"
        return self.invoice_number
    
    @property
    def is_invoice_sent(self):
        """Check if invoice has been sent."""
        return self.sent_at is not None
    
    def __repr__(self):
        return f'<MonthlyBilling shop={self.shop_id} {self.period_display} {self.total_amount}円>'
