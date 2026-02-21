"""
Night-Walk - メールテンプレート管理モデル
管理画面からメール文面を編集可能にする
"""
from datetime import datetime
from ..extensions import db


class EmailTemplate(db.Model):
    """メールテンプレート"""
    __tablename__ = 'email_templates'
    
    # テンプレートキー（固定識別子）
    KEY_SHOP_APPROVAL = 'shop_approval'        # 店舗承認通知
    KEY_SHOP_REJECTION = 'shop_rejection'      # 店舗却下通知
    
    TEMPLATE_KEYS = {
        KEY_SHOP_APPROVAL: '店舗承認通知メール',
        KEY_SHOP_REJECTION: '店舗却下通知メール',
    }
    
    # 各テンプレートで使用可能なプレースホルダー
    PLACEHOLDERS = {
        KEY_SHOP_APPROVAL: {
            '{owner_name}': 'オーナー名',
            '{shop_name}': '店舗名',
            '{email}': 'ログインメールアドレス',
            '{temp_password}': '仮パスワード',
            '{login_url}': 'ログインURL',
        },
        KEY_SHOP_REJECTION: {
            '{owner_name}': 'オーナー名',
            '{shop_name}': '店舗名',
            '{reason}': '却下理由',
        },
    }
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)  # テンプレート名（表示用）
    subject = db.Column(db.String(200), nullable=False)  # メール件名
    body_html = db.Column(db.Text, nullable=False)  # メール本文（HTML）
    
    is_active = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    
    @classmethod
    def get_template(cls, key):
        """テンプレートを取得（なければデフォルトを作成）"""
        template = cls.query.filter_by(key=key).first()
        if not template:
            template = cls._create_default(key)
        return template
    
    @classmethod
    def _create_default(cls, key):
        """デフォルトテンプレートを作成"""
        defaults = cls._get_defaults()
        if key not in defaults:
            return None
        
        default = defaults[key]
        template = cls(
            key=key,
            name=default['name'],
            subject=default['subject'],
            body_html=default['body_html'],
        )
        db.session.add(template)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            # 同時作成の場合、既存を返す
            return cls.query.filter_by(key=key).first()
        return template
    
    def render_subject(self, **kwargs):
        """件名にプレースホルダーを適用"""
        result = self.subject
        for key, value in kwargs.items():
            result = result.replace('{' + key + '}', str(value) if value else '')
        return result
    
    def render_body(self, **kwargs):
        """本文にプレースホルダーを適用"""
        result = self.body_html
        for key, value in kwargs.items():
            result = result.replace('{' + key + '}', str(value) if value else '')
        return result
    
    @classmethod
    def _get_defaults(cls):
        """デフォルトテンプレートの定義"""
        return {
            cls.KEY_SHOP_APPROVAL: {
                'name': '店舗承認通知メール',
                'subject': '【Night-Walk】店舗掲載審査完了のお知らせ - {shop_name}',
                'body_html': '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            background: linear-gradient(135deg, #FFD700, #FF6B6B);
            color: #000;
            padding: 20px;
            text-align: center;
            border-radius: 8px 8px 0 0;
        }
        .content {
            background: #f9f9f9;
            padding: 30px;
            border: 1px solid #ddd;
            border-top: none;
            border-radius: 0 0 8px 8px;
        }
        .login-box {
            background: #fff;
            border: 2px solid #FFD700;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
        }
        .login-box h3 {
            margin-top: 0;
            color: #FFD700;
        }
        .credential {
            background: #f5f5f5;
            padding: 10px 15px;
            margin: 10px 0;
            border-radius: 4px;
            font-family: monospace;
        }
        .btn {
            display: inline-block;
            background: #FFD700;
            color: #000;
            padding: 12px 30px;
            text-decoration: none;
            border-radius: 6px;
            font-weight: bold;
            margin: 20px 0;
        }
        .footer {
            text-align: center;
            color: #666;
            font-size: 12px;
            margin-top: 30px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Night-Walk</h1>
    </div>
    <div class="content">
        <h2>{owner_name} 様</h2>
        
        <p>
            この度は Night-Walk への店舗掲載をお申し込みいただき、誠にありがとうございます。<br>
            審査が完了し、<strong>「{shop_name}」</strong>の掲載が承認されましたのでお知らせいたします。
        </p>
        
        <div class="login-box">
            <h3>ログイン情報</h3>
            <p><strong>メールアドレス（ID）:</strong></p>
            <div class="credential">{email}</div>
            
            <p><strong>仮パスワード:</strong></p>
            <div class="credential">{temp_password}</div>
            
            <p style="color: #e74c3c; font-size: 14px;">
                ※ 初回ログイン後、必ずパスワードを変更してください。
            </p>
        </div>
        
        <p style="text-align: center;">
            <a href="{login_url}" class="btn">管理画面にログイン</a>
        </p>
        
        <h3>ログイン後の初期設定</h3>
        <ol>
            <li>店舗情報の詳細入力（営業時間、料金、紹介文など）</li>
            <li>店舗画像のアップロード</li>
            <li>キャスト情報の登録（任意）</li>
            <li>空席状況を「空」に変更 → 公開開始！</li>
        </ol>
        
        <p>
            ご不明点がございましたら、お気軽にお問い合わせください。<br>
            今後ともNight-Walkをよろしくお願いいたします。
        </p>
    </div>
    <div class="footer">
        <p>
            Night-Walk運営事務局<br>
            <a href="mailto:yorutabi2025@gmail.com">yorutabi2025@gmail.com</a>
        </p>
        <p>
            ※ このメールは自動送信されています。
        </p>
    </div>
</body>
</html>'''
            },
            cls.KEY_SHOP_REJECTION: {
                'name': '店舗却下通知メール',
                'subject': '【Night-Walk】店舗掲載審査結果のお知らせ - {shop_name}',
                'body_html': '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            background: #666;
            color: #fff;
            padding: 20px;
            text-align: center;
            border-radius: 8px 8px 0 0;
        }
        .content {
            background: #f9f9f9;
            padding: 30px;
            border: 1px solid #ddd;
            border-top: none;
            border-radius: 0 0 8px 8px;
        }
        .reason-box {
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 20px 0;
        }
        .footer {
            text-align: center;
            color: #666;
            font-size: 12px;
            margin-top: 30px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Night-Walk</h1>
    </div>
    <div class="content">
        <h2>{owner_name} 様</h2>
        
        <p>
            この度は Night-Walk への店舗掲載をお申し込みいただき、誠にありがとうございます。<br>
            審査の結果、誠に恐れ入りますが、今回は掲載を見送らせていただくこととなりました。
        </p>
        
        <div class="reason-box">
            <strong>理由:</strong><br>
            {reason}
        </div>
        
        <p>
            ご不明点がございましたら、お気軽にお問い合わせください。
        </p>
    </div>
    <div class="footer">
        <p>
            Night-Walk運営事務局<br>
            <a href="mailto:yorutabi2025@gmail.com">yorutabi2025@gmail.com</a>
        </p>
    </div>
</body>
</html>'''
            },
        }
