# app/models/cast_shift.py
"""キャスト出勤シフト管理モデル"""

from datetime import datetime, date, time, timedelta
from ..extensions import db


class CastShift(db.Model):
    """キャスト出勤シフト"""
    __tablename__ = 'cast_shifts'
    
    # シフトステータス
    STATUS_SCHEDULED = 'scheduled'   # 予定
    STATUS_CONFIRMED = 'confirmed'   # 確定
    STATUS_WORKING = 'working'       # 出勤中
    STATUS_FINISHED = 'finished'     # 終了
    STATUS_CANCELED = 'canceled'     # キャンセル
    
    STATUSES = [STATUS_SCHEDULED, STATUS_CONFIRMED, STATUS_WORKING, STATUS_FINISHED, STATUS_CANCELED]
    
    STATUS_LABELS = {
        STATUS_SCHEDULED: '予定',
        STATUS_CONFIRMED: '確定',
        STATUS_WORKING: '出勤中',
        STATUS_FINISHED: '終了',
        STATUS_CANCELED: 'キャンセル',
    }
    
    id = db.Column(db.Integer, primary_key=True)
    cast_id = db.Column(db.Integer, db.ForeignKey('casts.id', ondelete='CASCADE'), nullable=False, index=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # シフト日時
    shift_date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.Time)  # null = 未定
    end_time = db.Column(db.Time)    # null = 未定
    
    # ステータス
    status = db.Column(db.String(20), nullable=False, default=STATUS_SCHEDULED, index=True)
    
    # 備考
    note = db.Column(db.String(255))
    
    # 監査
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーション
    cast = db.relationship('Cast', backref=db.backref('shifts', lazy='dynamic'))
    shop = db.relationship('Shop', backref=db.backref('cast_shifts', lazy='dynamic'))
    
    __table_args__ = (
        db.UniqueConstraint('cast_id', 'shift_date', name='uq_cast_shift_date'),
        db.Index('ix_shift_date_shop', 'shift_date', 'shop_id'),
    )
    
    @property
    def status_label(self):
        """ステータス表示名"""
        return self.STATUS_LABELS.get(self.status, self.status)
    
    @property
    def time_display(self):
        """時間表示（例: 20:00〜02:00）"""
        if not self.start_time and not self.end_time:
            return '未定'
        
        start = self.start_time.strftime('%H:%M') if self.start_time else '--:--'
        end = self.end_time.strftime('%H:%M') if self.end_time else '--:--'
        return f'{start}〜{end}'
    
    @property
    def is_today(self):
        """今日のシフトか"""
        return self.shift_date == date.today()
    
    @property
    def is_future(self):
        """将来のシフトか"""
        return self.shift_date > date.today()
    
    @property
    def is_past(self):
        """過去のシフトか"""
        return self.shift_date < date.today()
    
    @property
    def is_currently_working(self):
        """現在出勤中か"""
        if self.status != self.STATUS_WORKING:
            return False
        
        if self.shift_date != date.today():
            return False
        
        # 時間指定がない場合は出勤中とみなす
        if not self.start_time:
            return True
        
        now = datetime.now().time()
        
        # 終了時間が翌日にまたがる場合の処理
        if self.end_time and self.end_time < self.start_time:
            # 深夜跨ぎ（例: 20:00〜02:00）
            return now >= self.start_time or now <= self.end_time
        
        # 通常（例: 18:00〜23:00）
        if self.end_time:
            return self.start_time <= now <= self.end_time
        
        return now >= self.start_time
    
    @classmethod
    def get_today_shifts(cls, shop_id):
        """今日の出勤シフトを取得"""
        return cls.query.filter(
            cls.shop_id == shop_id,
            cls.shift_date == date.today(),
            cls.status.in_([cls.STATUS_CONFIRMED, cls.STATUS_WORKING])
        ).order_by(cls.start_time).all()
    
    @classmethod
    def get_working_now(cls, shop_id):
        """現在出勤中のキャストを取得"""
        shifts = cls.get_today_shifts(shop_id)
        return [s for s in shifts if s.is_currently_working or s.status == cls.STATUS_WORKING]
    
    @classmethod
    def get_week_shifts(cls, shop_id, start_date=None):
        """週間シフトを取得"""
        if not start_date:
            start_date = date.today()
        
        end_date = start_date + timedelta(days=7)
        
        return cls.query.filter(
            cls.shop_id == shop_id,
            cls.shift_date >= start_date,
            cls.shift_date < end_date,
            cls.status != cls.STATUS_CANCELED
        ).order_by(cls.shift_date, cls.start_time).all()
    
    @classmethod
    def get_cast_shifts(cls, cast_id, start_date=None, end_date=None):
        """キャストの出勤シフトを取得"""
        query = cls.query.filter(cls.cast_id == cast_id)
        
        if start_date:
            query = query.filter(cls.shift_date >= start_date)
        
        if end_date:
            query = query.filter(cls.shift_date <= end_date)
        
        return query.order_by(cls.shift_date.desc()).all()
    
    @classmethod
    def create_or_update(cls, cast_id, shop_id, shift_date, start_time=None, 
                         end_time=None, status=None, note=None, user_id=None):
        """シフトを作成または更新"""
        existing = cls.query.filter_by(cast_id=cast_id, shift_date=shift_date).first()
        
        if existing:
            if start_time is not None:
                existing.start_time = start_time
            if end_time is not None:
                existing.end_time = end_time
            if status is not None:
                existing.status = status
            if note is not None:
                existing.note = note
            existing.updated_at = datetime.utcnow()
            return existing
        
        shift = cls(
            cast_id=cast_id,
            shop_id=shop_id,
            shift_date=shift_date,
            start_time=start_time,
            end_time=end_time,
            status=status or cls.STATUS_SCHEDULED,
            note=note,
            created_by=user_id
        )
        db.session.add(shift)
        return shift
    
    @classmethod
    def bulk_create_week(cls, cast_id, shop_id, shifts_data, user_id=None):
        """
        週間シフトを一括作成
        
        Args:
            shifts_data: [{'date': date, 'start': time, 'end': time}, ...]
        """
        results = []
        for data in shifts_data:
            shift = cls.create_or_update(
                cast_id=cast_id,
                shop_id=shop_id,
                shift_date=data['date'],
                start_time=data.get('start'),
                end_time=data.get('end'),
                status=cls.STATUS_SCHEDULED,
                user_id=user_id
            )
            results.append(shift)
        return results
    
    def start_working(self):
        """出勤開始"""
        self.status = self.STATUS_WORKING
        if not self.start_time:
            self.start_time = datetime.now().time()
    
    def finish_working(self):
        """退勤"""
        self.status = self.STATUS_FINISHED
        if not self.end_time:
            self.end_time = datetime.now().time()
    
    def cancel(self, reason=None):
        """シフトキャンセル"""
        self.status = self.STATUS_CANCELED
        if reason:
            self.note = f'{self.note or ""} [キャンセル理由: {reason}]'.strip()
    
    def __repr__(self):
        return f'<CastShift cast={self.cast_id} date={self.shift_date}>'


class ShiftTemplate(db.Model):
    """シフトテンプレート（繰り返し設定用）"""
    __tablename__ = 'shift_templates'
    
    # 曜日
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6
    
    DAY_LABELS = {
        MONDAY: '月',
        TUESDAY: '火',
        WEDNESDAY: '水',
        THURSDAY: '木',
        FRIDAY: '金',
        SATURDAY: '土',
        SUNDAY: '日',
    }
    
    id = db.Column(db.Integer, primary_key=True)
    cast_id = db.Column(db.Integer, db.ForeignKey('casts.id', ondelete='CASCADE'), nullable=False, index=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # 曜日（0=月曜、6=日曜）
    day_of_week = db.Column(db.Integer, nullable=False)
    
    # 時間
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーション
    cast = db.relationship('Cast', backref=db.backref('shift_templates', lazy='dynamic'))
    
    __table_args__ = (
        db.UniqueConstraint('cast_id', 'day_of_week', name='uq_cast_template_day'),
    )
    
    @property
    def day_label(self):
        """曜日表示"""
        return self.DAY_LABELS.get(self.day_of_week, '')
    
    @classmethod
    def get_templates(cls, cast_id):
        """キャストのテンプレートを取得"""
        return cls.query.filter_by(cast_id=cast_id, is_active=True)\
            .order_by(cls.day_of_week).all()
    
    @classmethod
    def apply_template(cls, cast_id, shop_id, start_date, weeks=4, user_id=None):
        """テンプレートを適用してシフトを生成"""
        templates = cls.get_templates(cast_id)
        if not templates:
            return []
        
        template_map = {t.day_of_week: t for t in templates}
        results = []
        
        for week in range(weeks):
            for day in range(7):
                current_date = start_date + timedelta(days=week * 7 + day)
                weekday = current_date.weekday()
                
                if weekday in template_map:
                    template = template_map[weekday]
                    shift = CastShift.create_or_update(
                        cast_id=cast_id,
                        shop_id=shop_id,
                        shift_date=current_date,
                        start_time=template.start_time,
                        end_time=template.end_time,
                        status=CastShift.STATUS_SCHEDULED,
                        user_id=user_id
                    )
                    results.append(shift)
        
        return results
    
    def __repr__(self):
        return f'<ShiftTemplate cast={self.cast_id} day={self.day_of_week}>'
