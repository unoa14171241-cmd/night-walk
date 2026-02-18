# app/models/cast_tag.py
"""キャストタグモデル（接客タイプ、趣味、特技など）"""

from datetime import datetime
from ..extensions import db


class CastTag(db.Model):
    """キャストのタグ"""
    __tablename__ = 'cast_tags'
    
    # タグカテゴリ
    CATEGORY_SERVICE = 'service'        # 接客タイプ
    CATEGORY_HOBBY = 'hobby'            # 趣味
    CATEGORY_SKILL = 'skill'            # 特技
    CATEGORY_PERSONALITY = 'personality' # 性格
    CATEGORY_OTHER = 'other'            # その他
    
    CATEGORIES = [CATEGORY_SERVICE, CATEGORY_HOBBY, CATEGORY_SKILL, CATEGORY_PERSONALITY, CATEGORY_OTHER]
    
    CATEGORY_LABELS = {
        CATEGORY_SERVICE: '接客タイプ',
        CATEGORY_HOBBY: '趣味',
        CATEGORY_SKILL: '特技',
        CATEGORY_PERSONALITY: '性格',
        CATEGORY_OTHER: 'その他',
    }
    
    CATEGORY_ICONS = {
        CATEGORY_SERVICE: '🍸',
        CATEGORY_HOBBY: '🎮',
        CATEGORY_SKILL: '⭐',
        CATEGORY_PERSONALITY: '💎',
        CATEGORY_OTHER: '🏷️',
    }
    
    # よく使われるタグのプリセット
    PRESET_TAGS = {
        CATEGORY_SERVICE: [
            '明るい接客', '落ち着いた接客', '話し上手', '聞き上手',
            '盛り上げ上手', 'お酒に詳しい', 'カラオケ好き', '初心者歓迎',
        ],
        CATEGORY_HOBBY: [
            '音楽', '映画', 'アニメ', 'ゲーム', '旅行', 'グルメ',
            'ファッション', 'スポーツ', '読書', 'カフェ巡り', '推し活',
        ],
        CATEGORY_SKILL: [
            'ダンス', '歌', '楽器演奏', '料理', 'ネイル',
            'マッサージ', '占い', '手品', '語学',
        ],
        CATEGORY_PERSONALITY: [
            '明るい', '優しい', '面白い', 'クール', '甘えん坊',
            'ミステリアス', '天然', 'しっかり者', 'ムードメーカー',
        ],
    }
    
    id = db.Column(db.Integer, primary_key=True)
    cast_id = db.Column(db.Integer, db.ForeignKey('casts.id', ondelete='CASCADE'), nullable=False, index=True)
    
    category = db.Column(db.String(30), nullable=False, default=CATEGORY_OTHER)
    name = db.Column(db.String(50), nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーション
    cast = db.relationship('Cast', backref=db.backref('tags', lazy='dynamic', cascade='all, delete-orphan'))
    
    __table_args__ = (
        db.UniqueConstraint('cast_id', 'category', 'name', name='uq_cast_tag'),
    )
    
    @property
    def category_label(self):
        return self.CATEGORY_LABELS.get(self.category, self.category)
    
    @property
    def category_icon(self):
        return self.CATEGORY_ICONS.get(self.category, '🏷️')
    
    @classmethod
    def get_tags_by_cast(cls, cast_id):
        """キャストのタグをカテゴリ別に取得"""
        tags = cls.query.filter_by(cast_id=cast_id).order_by(cls.category, cls.name).all()
        result = {}
        for tag in tags:
            if tag.category not in result:
                result[tag.category] = []
            result[tag.category].append(tag)
        return result
    
    @classmethod
    def set_tags(cls, cast_id, category, tag_names):
        """指定カテゴリのタグを一括設定（既存を削除して再作成）"""
        cls.query.filter_by(cast_id=cast_id, category=category).delete()
        for name in tag_names:
            name = name.strip()
            if name:
                tag = cls(cast_id=cast_id, category=category, name=name)
                db.session.add(tag)
    
    def __repr__(self):
        return f'<CastTag {self.category}:{self.name}>'
