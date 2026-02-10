# app/models/referral.py
"""紹介制度モデル - 紹介で無料延長（最大2ヶ月）"""

from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import secrets
import string
from ..extensions import db


class ShopReferral(db.Model):
    """店舗紹介（紹介で無料延長）"""
    __tablename__ = 'shop_referrals'
    
    # 紹介コードの文字数
    CODE_LENGTH = 8
    
    # 1紹介あたりの無料延長月数
    FREE_MONTHS_PER_REFERRAL = 1
    
    # 最大無料延長月数
    MAX_FREE_MONTHS = 2
    
    # ステータス
    STATUS_PENDING = 'pending'      # 紹介待ち（コード発行済み、未使用）
    STATUS_USED = 'used'            # 使用済み
    STATUS_EXPIRED = 'expired'      # 期限切れ
    STATUS_REWARDED = 'rewarded'    # 特典付与済み
    
    STATUS_LABELS = {
        STATUS_PENDING: '未使用',
        STATUS_USED: '使用済み',
        STATUS_EXPIRED: '期限切れ',
        STATUS_REWARDED: '特典付与済み',
    }
    
    id = db.Column(db.Integer, primary_key=True)
    
    # 紹介元店舗
    referrer_shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=False, index=True)
    
    # 紹介コード（ユニーク）
    referral_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    
    # 紹介先店舗（使用時に記録）
    referred_shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), index=True)
    
    # ステータス
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING, index=True)
    
    # 使用日時
    used_at = db.Column(db.DateTime)
    
    # 特典付与日時
    rewarded_at = db.Column(db.DateTime)
    
    # 無料延長月数（付与された月数）
    free_months_granted = db.Column(db.Integer, default=0)
    
    # 有効期限（コード発行から30日等）
    expires_at = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーション
    referrer_shop = db.relationship('Shop', foreign_keys=[referrer_shop_id], 
                                     backref=db.backref('referrals_made', lazy='dynamic'))
    referred_shop = db.relationship('Shop', foreign_keys=[referred_shop_id],
                                     backref=db.backref('referral_used', uselist=False))
    
    @property
    def status_label(self):
        """ステータス表示名"""
        return self.STATUS_LABELS.get(self.status, self.status)
    
    @property
    def is_valid(self):
        """コードが有効か（未使用かつ期限内）"""
        if self.status != self.STATUS_PENDING:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True
    
    @classmethod
    def generate_code(cls):
        """ユニークな紹介コードを生成"""
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(secrets.choice(chars) for _ in range(cls.CODE_LENGTH))
            # 重複チェック
            if not cls.query.filter_by(referral_code=code).first():
                return code
    
    @classmethod
    def create_for_shop(cls, shop_id, expires_days=30):
        """
        店舗用の紹介コードを作成
        
        Args:
            shop_id: 紹介元店舗ID
            expires_days: 有効期限（日数）
        
        Returns:
            ShopReferral
        """
        referral = cls(
            referrer_shop_id=shop_id,
            referral_code=cls.generate_code(),
            expires_at=datetime.utcnow() + relativedelta(days=expires_days)
        )
        db.session.add(referral)
        return referral
    
    @classmethod
    def get_by_code(cls, code):
        """コードから紹介レコードを取得"""
        return cls.query.filter_by(referral_code=code.upper()).first()
    
    @classmethod
    def use_code(cls, code, referred_shop_id):
        """
        紹介コードを使用
        
        Args:
            code: 紹介コード
            referred_shop_id: 紹介された店舗ID
        
        Returns:
            tuple: (success: bool, referral: ShopReferral or None, error: str or None)
        """
        referral = cls.get_by_code(code)
        
        if not referral:
            return False, None, '紹介コードが見つかりません'
        
        if not referral.is_valid:
            if referral.status == cls.STATUS_USED:
                return False, None, 'この紹介コードは既に使用されています'
            elif referral.status == cls.STATUS_EXPIRED:
                return False, None, 'この紹介コードは期限切れです'
            else:
                return False, None, 'この紹介コードは無効です'
        
        # 自分自身の紹介は不可
        if referral.referrer_shop_id == referred_shop_id:
            return False, None, '自分自身の紹介コードは使用できません'
        
        # 既に紹介を受けている場合は不可
        existing = cls.query.filter_by(
            referred_shop_id=referred_shop_id,
            status=cls.STATUS_USED
        ).first()
        if existing:
            return False, None, 'この店舗は既に紹介を受けています'
        
        # コードを使用済みにする
        referral.referred_shop_id = referred_shop_id
        referral.status = cls.STATUS_USED
        referral.used_at = datetime.utcnow()
        
        return True, referral, None
    
    def grant_reward(self):
        """
        紹介特典を付与（紹介元店舗に無料延長）
        
        Returns:
            tuple: (success: bool, months_granted: int, error: str or None)
        """
        if self.status != self.STATUS_USED:
            return False, 0, '紹介がまだ使用されていません'
        
        if self.status == self.STATUS_REWARDED:
            return False, 0, '特典は既に付与されています'
        
        # 紹介元店舗の現在の無料延長月数を確認
        referrer = self.referrer_shop
        if not referrer:
            return False, 0, '紹介元店舗が見つかりません'
        
        # 累計無料延長月数を計算
        total_granted = db.session.query(
            db.func.coalesce(db.func.sum(ShopReferral.free_months_granted), 0)
        ).filter(
            ShopReferral.referrer_shop_id == self.referrer_shop_id,
            ShopReferral.status == self.STATUS_REWARDED
        ).scalar()
        
        if total_granted >= self.MAX_FREE_MONTHS:
            return False, 0, f'無料延長は最大{self.MAX_FREE_MONTHS}ヶ月までです'
        
        # 付与可能な月数
        months_to_grant = min(
            self.FREE_MONTHS_PER_REFERRAL,
            self.MAX_FREE_MONTHS - total_granted
        )
        
        # 特典付与
        self.free_months_granted = months_to_grant
        self.status = self.STATUS_REWARDED
        self.rewarded_at = datetime.utcnow()
        
        # 店舗のキャンペーン設定を更新
        if not referrer.campaign_free_months:
            referrer.campaign_free_months = 0
        referrer.campaign_free_months += months_to_grant
        
        if not referrer.campaign_notes:
            referrer.campaign_notes = ''
        referrer.campaign_notes += f'\n紹介特典: {months_to_grant}ヶ月無料 ({datetime.utcnow().strftime("%Y-%m-%d")})'
        
        return True, months_to_grant, None
    
    @classmethod
    def get_shop_referral_stats(cls, shop_id):
        """
        店舗の紹介統計を取得
        
        Returns:
            dict: {
                'codes_created': int,
                'codes_used': int,
                'total_free_months': int,
                'remaining_free_months': int
            }
        """
        codes_created = cls.query.filter_by(referrer_shop_id=shop_id).count()
        codes_used = cls.query.filter_by(
            referrer_shop_id=shop_id,
            status=cls.STATUS_USED
        ).count() + cls.query.filter_by(
            referrer_shop_id=shop_id,
            status=cls.STATUS_REWARDED
        ).count()
        
        total_granted = db.session.query(
            db.func.coalesce(db.func.sum(cls.free_months_granted), 0)
        ).filter(
            cls.referrer_shop_id == shop_id,
            cls.status == cls.STATUS_REWARDED
        ).scalar()
        
        remaining = max(0, cls.MAX_FREE_MONTHS - total_granted)
        
        return {
            'codes_created': codes_created,
            'codes_used': codes_used,
            'total_free_months': total_granted,
            'remaining_free_months': remaining
        }
    
    @classmethod
    def get_active_codes(cls, shop_id):
        """店舗の有効なコード一覧を取得"""
        return cls.query.filter(
            cls.referrer_shop_id == shop_id,
            cls.status == cls.STATUS_PENDING,
            (cls.expires_at == None) | (cls.expires_at > datetime.utcnow())
        ).order_by(cls.created_at.desc()).all()
    
    @classmethod
    def expire_old_codes(cls):
        """期限切れコードを一括更新"""
        now = datetime.utcnow()
        expired = cls.query.filter(
            cls.status == cls.STATUS_PENDING,
            cls.expires_at != None,
            cls.expires_at < now
        ).all()
        
        for ref in expired:
            ref.status = cls.STATUS_EXPIRED
        
        return len(expired)
    
    def __repr__(self):
        return f'<ShopReferral {self.referral_code} from={self.referrer_shop_id}>'
