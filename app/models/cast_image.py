# app/models/cast_image.py
"""キャスト画像モデル（複数枚対応）"""

from datetime import datetime
from flask import url_for
from ..extensions import db


class CastImage(db.Model):
    """キャストの写真（複数枚対応）"""
    __tablename__ = 'cast_images'
    
    id = db.Column(db.Integer, primary_key=True)
    cast_id = db.Column(db.Integer, db.ForeignKey('casts.id', ondelete='CASCADE'), nullable=False, index=True)
    
    filename = db.Column(db.String(255), nullable=False)
    is_main = db.Column(db.Boolean, default=False)  # メイン画像フラグ
    sort_order = db.Column(db.Integer, default=0)
    caption = db.Column(db.String(200))  # 画像キャプション
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーション
    cast = db.relationship('Cast', backref=db.backref(
        'gallery_images', lazy='dynamic',
        cascade='all, delete-orphan',
        order_by='CastImage.sort_order'
    ))
    
    @property
    def url(self):
        """画像URLを返す（DB/Cloudinary/ローカル対応）"""
        if not self.filename:
            return None
        
        # DB保存形式 (folder/file.ext)
        if '/' in self.filename:
            return f'/images_db/{self.filename}'
        
        # Cloudinary public_id形式
        if self.filename.startswith('night-walk/') or self.filename.startswith('http'):
            if self.filename.startswith('http'):
                return self.filename
            from flask import current_app
            cloud_name = current_app.config.get('CLOUDINARY_CLOUD_NAME')
            if cloud_name:
                return f"https://res.cloudinary.com/{cloud_name}/image/upload/{self.filename}"
        
        return f'/static/uploads/casts/{self.filename}'
    
    @classmethod
    def get_main_image(cls, cast_id):
        """メイン画像を取得"""
        return cls.query.filter_by(cast_id=cast_id, is_main=True).first()
    
    @classmethod
    def get_gallery(cls, cast_id):
        """ギャラリー画像一覧を取得"""
        return cls.query.filter_by(cast_id=cast_id).order_by(
            cls.is_main.desc(), cls.sort_order
        ).all()
    
    @classmethod
    def set_main(cls, image_id, cast_id):
        """メイン画像を設定（他のis_mainをFalseに）"""
        cls.query.filter_by(cast_id=cast_id).update({cls.is_main: False})
        image = cls.query.get(image_id)
        if image and image.cast_id == cast_id:
            image.is_main = True
    
    def __repr__(self):
        return f'<CastImage {self.id} cast={self.cast_id}>'
