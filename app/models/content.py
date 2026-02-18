"""
Night-Walk MVP - Content Models (Announcements, Advertisements)
"""
from datetime import datetime
from ..extensions import db


class Announcement(db.Model):
    """Announcement/News model for public display."""
    __tablename__ = 'announcements'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    link_url = db.Column(db.String(500))
    link_text = db.Column(db.String(100))  # リンクテキスト（例: "詳細を見る"）
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    priority = db.Column(db.Integer, default=0)  # 表示順（大きいほど上）
    starts_at = db.Column(db.DateTime)  # 表示開始日時
    ends_at = db.Column(db.DateTime)    # 表示終了日時
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @classmethod
    def get_active(cls, limit=5):
        """Get active announcements."""
        now = datetime.utcnow()
        query = cls.query.filter_by(is_active=True)
        query = query.filter(
            (cls.starts_at == None) | (cls.starts_at <= now)
        )
        query = query.filter(
            (cls.ends_at == None) | (cls.ends_at >= now)
        )
        return query.order_by(cls.priority.desc(), cls.created_at.desc()).limit(limit).all()
    
    @property
    def is_currently_active(self):
        """Check if announcement is currently active."""
        if not self.is_active:
            return False
        now = datetime.utcnow()
        if self.starts_at and self.starts_at > now:
            return False
        if self.ends_at and self.ends_at < now:
            return False
        return True
    
    def __repr__(self):
        return f'<Announcement {self.title}>'


class Advertisement(db.Model):
    """Advertisement/Banner model for public display."""
    __tablename__ = 'advertisements'
    
    # Position types
    POSITION_TOP = 'top'           # ページ上部（メインバナー）
    POSITION_SIDEBAR = 'sidebar'   # サイドバー
    POSITION_BOTTOM = 'bottom'     # ページ下部
    POSITION_INLINE = 'inline'     # 店舗一覧内
    
    POSITIONS = [POSITION_TOP, POSITION_SIDEBAR, POSITION_BOTTOM, POSITION_INLINE]
    POSITION_LABELS = {
        POSITION_TOP: 'トップバナー',
        POSITION_SIDEBAR: 'サイドバー',
        POSITION_BOTTOM: 'ページ下部',
        POSITION_INLINE: '一覧内広告',
    }
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    image_url = db.Column(db.String(500))
    image_filename = db.Column(db.String(255))  # アップロードされた画像
    link_url = db.Column(db.String(500))
    position = db.Column(db.String(50), nullable=False, default=POSITION_TOP, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    priority = db.Column(db.Integer, default=0)
    click_count = db.Column(db.Integer, default=0)  # クリック数
    starts_at = db.Column(db.DateTime)
    ends_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @classmethod
    def get_active(cls, position=None, limit=10):
        """Get active advertisements."""
        now = datetime.utcnow()
        query = cls.query.filter_by(is_active=True)
        if position:
            query = query.filter_by(position=position)
        query = query.filter(
            (cls.starts_at == None) | (cls.starts_at <= now)
        )
        query = query.filter(
            (cls.ends_at == None) | (cls.ends_at >= now)
        )
        return query.order_by(cls.priority.desc(), cls.created_at.desc()).limit(limit).all()
    
    @property
    def display_image_url(self):
        """Get the image URL for display (cloud, database, or local)."""
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
            return f'/static/uploads/ads/{self.image_filename}'
        return self.image_url
    
    @property
    def is_currently_active(self):
        """Check if advertisement is currently active."""
        if not self.is_active:
            return False
        now = datetime.utcnow()
        if self.starts_at and self.starts_at > now:
            return False
        if self.ends_at and self.ends_at < now:
            return False
        return True
    
    def record_click(self):
        """Record a click on this advertisement."""
        self.click_count = (self.click_count or 0) + 1
    
    def __repr__(self):
        return f'<Advertisement {self.title}>'
