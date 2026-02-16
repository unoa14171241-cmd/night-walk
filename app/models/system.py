"""
Night-Walk - システム管理モデル
障害対応・ステータス管理・不適切コンテンツ管理
"""
from datetime import datetime
from ..extensions import db


class SystemStatus(db.Model):
    """システムステータス（障害情報・メンテナンス）"""
    __tablename__ = 'system_status'
    
    # ステータスタイプ
    STATUS_NORMAL = 'normal'           # 正常稼働
    STATUS_DEGRADED = 'degraded'       # 一部障害
    STATUS_MAINTENANCE = 'maintenance' # メンテナンス中
    STATUS_OUTAGE = 'outage'           # 全面障害
    
    STATUS_LABELS = {
        STATUS_NORMAL: '正常稼働',
        STATUS_DEGRADED: '一部障害',
        STATUS_MAINTENANCE: 'メンテナンス中',
        STATUS_OUTAGE: '全面障害',
    }
    
    STATUS_COLORS = {
        STATUS_NORMAL: 'success',
        STATUS_DEGRADED: 'warning',
        STATUS_MAINTENANCE: 'info',
        STATUS_OUTAGE: 'danger',
    }
    
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_NORMAL)
    title = db.Column(db.String(200))  # 障害タイトル
    message = db.Column(db.Text)       # 詳細メッセージ
    affected_services = db.Column(db.String(500))  # 影響を受けるサービス（カンマ区切り）
    
    started_at = db.Column(db.DateTime)   # 障害開始時刻
    resolved_at = db.Column(db.DateTime)  # 解決時刻
    
    is_active = db.Column(db.Boolean, default=True)  # 現在表示中か
    notify_users = db.Column(db.Boolean, default=False)  # ユーザーに通知するか
    
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def status_label(self):
        return self.STATUS_LABELS.get(self.status, '不明')
    
    @property
    def status_color(self):
        return self.STATUS_COLORS.get(self.status, 'secondary')
    
    @property
    def is_resolved(self):
        return self.resolved_at is not None
    
    @property
    def duration_minutes(self):
        """障害継続時間（分）"""
        if not self.started_at:
            return 0
        end_time = self.resolved_at or datetime.utcnow()
        return int((end_time - self.started_at).total_seconds() / 60)
    
    @classmethod
    def get_current_status(cls):
        """現在のシステムステータスを取得"""
        active = cls.query.filter_by(is_active=True).order_by(cls.created_at.desc()).first()
        if active:
            return active
        # デフォルトで正常を返す
        return cls(status=cls.STATUS_NORMAL, title='正常稼働中')
    
    @classmethod
    def create_incident(cls, status, title, message=None, affected_services=None, user_id=None):
        """インシデントを作成"""
        incident = cls(
            status=status,
            title=title,
            message=message,
            affected_services=affected_services,
            started_at=datetime.utcnow(),
            is_active=True,
            created_by=user_id
        )
        db.session.add(incident)
        return incident


class ContentReport(db.Model):
    """不適切コンテンツ報告"""
    __tablename__ = 'content_reports'
    
    # コンテンツタイプ
    TYPE_SHOP_IMAGE = 'shop_image'
    TYPE_CAST_IMAGE = 'cast_image'
    TYPE_CAST_PROFILE = 'cast_profile'
    TYPE_SHOP_DESCRIPTION = 'shop_description'
    TYPE_REVIEW = 'review'
    
    # 報告理由
    REASON_INAPPROPRIATE = 'inappropriate'  # 不適切なコンテンツ
    REASON_ILLEGAL = 'illegal'              # 違法コンテンツ
    REASON_SPAM = 'spam'                    # スパム
    REASON_FAKE = 'fake'                    # 虚偽の情報
    REASON_COPYRIGHT = 'copyright'          # 著作権侵害
    REASON_OTHER = 'other'                  # その他
    
    REASON_LABELS = {
        REASON_INAPPROPRIATE: '不適切なコンテンツ',
        REASON_ILLEGAL: '違法コンテンツ',
        REASON_SPAM: 'スパム',
        REASON_FAKE: '虚偽の情報',
        REASON_COPYRIGHT: '著作権侵害',
        REASON_OTHER: 'その他',
    }
    
    # 対応ステータス
    STATUS_PENDING = 'pending'     # 未対応
    STATUS_REVIEWING = 'reviewing' # 確認中
    STATUS_HIDDEN = 'hidden'       # 非表示済み
    STATUS_DELETED = 'deleted'     # 削除済み
    STATUS_DISMISSED = 'dismissed' # 問題なし
    
    STATUS_LABELS = {
        STATUS_PENDING: '未対応',
        STATUS_REVIEWING: '確認中',
        STATUS_HIDDEN: '非表示済み',
        STATUS_DELETED: '削除済み',
        STATUS_DISMISSED: '問題なし',
    }
    
    id = db.Column(db.Integer, primary_key=True)
    content_type = db.Column(db.String(50), nullable=False)  # コンテンツタイプ
    content_id = db.Column(db.Integer, nullable=False)       # コンテンツID
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'))  # 関連店舗
    
    reason = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)  # 報告詳細
    
    reporter_type = db.Column(db.String(20))  # 'user', 'customer', 'anonymous'
    reporter_id = db.Column(db.Integer)       # 報告者ID
    reporter_ip = db.Column(db.String(45))    # 報告者IP
    
    status = db.Column(db.String(20), default=STATUS_PENDING)
    handled_by = db.Column(db.Integer, db.ForeignKey('users.id'))  # 対応者
    handled_at = db.Column(db.DateTime)
    handle_notes = db.Column(db.Text)  # 対応メモ
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @property
    def reason_label(self):
        return self.REASON_LABELS.get(self.reason, '不明')
    
    @property
    def status_label(self):
        return self.STATUS_LABELS.get(self.status, '不明')
    
    @classmethod
    def get_pending_count(cls):
        """未対応の報告数"""
        return cls.query.filter_by(status=cls.STATUS_PENDING).count()


class SystemLog(db.Model):
    """システムログ（障害追跡用）"""
    __tablename__ = 'system_logs'
    
    LEVEL_DEBUG = 'debug'
    LEVEL_INFO = 'info'
    LEVEL_WARNING = 'warning'
    LEVEL_ERROR = 'error'
    LEVEL_CRITICAL = 'critical'
    
    id = db.Column(db.Integer, primary_key=True)
    level = db.Column(db.String(20), nullable=False, index=True)
    category = db.Column(db.String(50), index=True)  # 'auth', 'payment', 'api', etc.
    message = db.Column(db.Text, nullable=False)
    details = db.Column(db.Text)  # JSON形式の詳細データ
    
    user_id = db.Column(db.Integer)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    request_path = db.Column(db.String(500))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    @classmethod
    def log(cls, level, category, message, details=None, user_id=None, ip=None, ua=None, path=None):
        """ログを記録"""
        log = cls(
            level=level,
            category=category,
            message=message,
            details=details,
            user_id=user_id,
            ip_address=ip,
            user_agent=ua,
            request_path=path
        )
        db.session.add(log)
        return log
    
    @classmethod
    def get_recent_errors(cls, limit=50):
        """最近のエラーログを取得"""
        return cls.query.filter(
            cls.level.in_([cls.LEVEL_ERROR, cls.LEVEL_CRITICAL])
        ).order_by(cls.created_at.desc()).limit(limit).all()


class DemoAccount(db.Model):
    """デモアカウント管理"""
    __tablename__ = 'demo_accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # デモ名（例: 営業用デモA）
    description = db.Column(db.Text)
    
    # 関連データ
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # デモ用ユーザー
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))  # デモ用カスタマー
    
    # ログイン情報（表示用）
    demo_email = db.Column(db.String(255))
    demo_password = db.Column(db.String(50))  # プレーンテキスト（デモ用）
    
    is_active = db.Column(db.Boolean, default=True)
    last_reset_at = db.Column(db.DateTime)  # 最終初期化日時
    
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    shop = db.relationship('Shop', foreign_keys=[shop_id])
    
    @classmethod
    def get_active_demos(cls):
        """有効なデモアカウント一覧"""
        return cls.query.filter_by(is_active=True).order_by(cls.name).all()


class ImageStore(db.Model):
    """データベース保存用画像データ (Render等の一時的なファイルシステム用)"""
    __tablename__ = 'image_store'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), unique=True, nullable=False, index=True)
    data = db.Column(db.LargeBinary, nullable=False)  # 画像バイナリデータ
    mimetype = db.Column(db.String(50))              # 例: 'image/jpeg'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @classmethod
    def save_image(cls, filename, data, mimetype=None):
        """画像を保存または更新"""
        existing = cls.query.filter_by(filename=filename).first()
        if existing:
            existing.data = data
            existing.mimetype = mimetype
            existing.created_at = datetime.utcnow()
            return existing
        
        new_image = cls(filename=filename, data=data, mimetype=mimetype)
        db.session.add(new_image)
        return new_image
    
    @classmethod
    def get_image(cls, filename):
        """画像データを取得"""
        return cls.query.filter_by(filename=filename).first()
    
    @classmethod
    def delete_image(cls, filename):
        """画像を削除"""
        image = cls.query.filter_by(filename=filename).first()
        if image:
            db.session.delete(image)
            return True
        return False
