# app/services/email_service.py
"""Night-Walk - Email Service via SendGrid"""

from flask import current_app, render_template


class EmailService:
    """General email service using SendGrid."""
    
    @classmethod
    def send_email(cls, to_email, subject, html_content, from_email=None):
        """
        Send email via SendGrid.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email body
            from_email: Sender email (optional, uses default)
        
        Returns:
            bool: Success status
        """
        import sendgrid
        from sendgrid.helpers.mail import Mail
        
        api_key = current_app.config.get('SENDGRID_API_KEY')
        
        if not api_key:
            current_app.logger.warning("SENDGRID_API_KEY not configured - email not sent")
            return False
        
        if not from_email:
            from_email = current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@night-walk.jp')
        
        sg = sendgrid.SendGridAPIClient(api_key=api_key)
        
        message = Mail(
            from_email=from_email,
            to_emails=to_email,
            subject=subject,
            html_content=html_content
        )
        
        try:
            response = sg.send(message)
            
            if response.status_code in [200, 201, 202]:
                current_app.logger.info(f"Email sent to {to_email}: {subject}")
                return True
            else:
                current_app.logger.error(f"SendGrid error: {response.status_code} - {response.body}")
                return False
                
        except Exception as e:
            current_app.logger.error(f"Failed to send email: {e}")
            return False
    
    @classmethod
    def send_shop_approval_notification(cls, shop, user, temp_password):
        """
        Send shop approval notification with login credentials.
        
        Args:
            shop: Shop instance
            user: User instance (shop owner)
            temp_password: Temporary password for first login
        
        Returns:
            bool: Success status
        """
        subject = f"【Night-Walk】店舗掲載審査完了のお知らせ - {shop.name}"
        
        # Get login URL
        try:
            from flask import url_for
            login_url = url_for('auth.login', _external=True)
        except Exception:
            login_url = "https://night-walk-ogrg.onrender.com/login"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background: linear-gradient(135deg, #FFD700, #FF6B6B);
                    color: #000;
                    padding: 20px;
                    text-align: center;
                    border-radius: 8px 8px 0 0;
                }}
                .content {{
                    background: #f9f9f9;
                    padding: 30px;
                    border: 1px solid #ddd;
                    border-top: none;
                    border-radius: 0 0 8px 8px;
                }}
                .login-box {{
                    background: #fff;
                    border: 2px solid #FFD700;
                    border-radius: 8px;
                    padding: 20px;
                    margin: 20px 0;
                }}
                .login-box h3 {{
                    margin-top: 0;
                    color: #FFD700;
                }}
                .credential {{
                    background: #f5f5f5;
                    padding: 10px 15px;
                    margin: 10px 0;
                    border-radius: 4px;
                    font-family: monospace;
                }}
                .btn {{
                    display: inline-block;
                    background: #FFD700;
                    color: #000;
                    padding: 12px 30px;
                    text-decoration: none;
                    border-radius: 6px;
                    font-weight: bold;
                    margin: 20px 0;
                }}
                .footer {{
                    text-align: center;
                    color: #666;
                    font-size: 12px;
                    margin-top: 30px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Night-Walk</h1>
            </div>
            <div class="content">
                <h2>{user.name} 様</h2>
                
                <p>
                    この度は Night-Walk への店舗掲載をお申し込みいただき、誠にありがとうございます。<br>
                    審査が完了し、<strong>「{shop.name}」</strong>の掲載が承認されましたのでお知らせいたします。
                </p>
                
                <div class="login-box">
                    <h3>ログイン情報</h3>
                    <p><strong>メールアドレス（ID）:</strong></p>
                    <div class="credential">{user.email}</div>
                    
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
        </html>
        """
        
        return cls.send_email(user.email, subject, html_content)
    
    @classmethod
    def send_shop_rejection_notification(cls, shop, user, reason):
        """
        Send shop rejection notification.
        
        Args:
            shop: Shop instance
            user: User instance (shop owner)
            reason: Rejection reason
        
        Returns:
            bool: Success status
        """
        subject = f"【Night-Walk】店舗掲載審査結果のお知らせ - {shop.name}"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background: #666;
                    color: #fff;
                    padding: 20px;
                    text-align: center;
                    border-radius: 8px 8px 0 0;
                }}
                .content {{
                    background: #f9f9f9;
                    padding: 30px;
                    border: 1px solid #ddd;
                    border-top: none;
                    border-radius: 0 0 8px 8px;
                }}
                .reason-box {{
                    background: #fff3cd;
                    border-left: 4px solid #ffc107;
                    padding: 15px;
                    margin: 20px 0;
                }}
                .footer {{
                    text-align: center;
                    color: #666;
                    font-size: 12px;
                    margin-top: 30px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Night-Walk</h1>
            </div>
            <div class="content">
                <h2>{user.name} 様</h2>
                
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
        </html>
        """
        
        return cls.send_email(user.email, subject, html_content)
