# app/models/cast_birthday.py
"""キャスト誕生日モデル（複数日対応）"""

from datetime import datetime, date
from ..extensions import db


class CastBirthday(db.Model):
    """キャストの誕生日（複数日設定可能）"""
    __tablename__ = 'cast_birthdays'
    
    id = db.Column(db.Integer, primary_key=True)
    cast_id = db.Column(db.Integer, db.ForeignKey('casts.id', ondelete='CASCADE'), nullable=False, index=True)
    
    birthday_month = db.Column(db.Integer, nullable=False)  # 月 (1-12)
    birthday_day = db.Column(db.Integer, nullable=False)     # 日 (1-31)
    label = db.Column(db.String(50))  # ラベル（例: "誕生日", "Night-Walk記念日"）
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーション
    cast = db.relationship('Cast', backref=db.backref(
        'birthdays', lazy='dynamic',
        cascade='all, delete-orphan',
        order_by='CastBirthday.birthday_month, CastBirthday.birthday_day'
    ))
    
    __table_args__ = (
        db.UniqueConstraint('cast_id', 'birthday_month', 'birthday_day', 'label', name='uq_cast_birthday'),
    )
    
    @property
    def display(self):
        """表示用文字列（例: 3/15）"""
        return f'{self.birthday_month}/{self.birthday_day}'
    
    @property
    def display_with_label(self):
        """ラベル付き表示（例: 3/15 (誕生日)）"""
        if self.label:
            return f'{self.display} ({self.label})'
        return self.display
    
    @property
    def is_today(self):
        """今日が誕生日かどうか"""
        today = date.today()
        return today.month == self.birthday_month and today.day == self.birthday_day
    
    @property
    def is_upcoming(self):
        """今後7日以内かどうか"""
        today = date.today()
        for i in range(7):
            d = today + __import__('datetime').timedelta(days=i)
            if d.month == self.birthday_month and d.day == self.birthday_day:
                return True
        return False
    
    @classmethod
    def get_birthdays(cls, cast_id):
        """キャストの誕生日一覧を取得"""
        return cls.query.filter_by(cast_id=cast_id).order_by(
            cls.birthday_month, cls.birthday_day
        ).all()
    
    @classmethod
    def get_today_birthdays(cls):
        """今日が誕生日のキャスト一覧"""
        today = date.today()
        return cls.query.filter_by(
            birthday_month=today.month,
            birthday_day=today.day
        ).all()
    
    def __repr__(self):
        return f'<CastBirthday {self.birthday_month}/{self.birthday_day}>'
