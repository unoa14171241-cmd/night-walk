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
        DBに保存されたテンプレートを使用（管理画面で編集可能）
        
        Args:
            shop: Shop instance
            user: User instance (shop owner)
            temp_password: Temporary password for first login
        
        Returns:
            bool: Success status
        """
        from ..models.email_template import EmailTemplate
        
        # Get login URL
        try:
            from flask import url_for
            login_url = url_for('auth.login', _external=True)
        except Exception:
            login_url = "https://night-walk-ogrg.onrender.com/login"
        
        # テンプレートをDBから取得（なければデフォルトが自動作成される）
        template = EmailTemplate.get_template(EmailTemplate.KEY_SHOP_APPROVAL)
        
        if not template:
            current_app.logger.error("Approval email template not found")
            return False
        
        # プレースホルダーを適用
        params = {
            'owner_name': user.name,
            'shop_name': shop.name,
            'email': user.email,
            'temp_password': temp_password,
            'login_url': login_url,
        }
        
        subject = template.render_subject(**params)
        html_content = template.render_body(**params)
        
        return cls.send_email(user.email, subject, html_content)
    
    @classmethod
    def send_shop_rejection_notification(cls, shop, user, reason):
        """
        Send shop rejection notification.
        DBに保存されたテンプレートを使用（管理画面で編集可能）
        
        Args:
            shop: Shop instance
            user: User instance (shop owner)
            reason: Rejection reason
        
        Returns:
            bool: Success status
        """
        from ..models.email_template import EmailTemplate
        
        # テンプレートをDBから取得
        template = EmailTemplate.get_template(EmailTemplate.KEY_SHOP_REJECTION)
        
        if not template:
            current_app.logger.error("Rejection email template not found")
            return False
        
        # プレースホルダーを適用
        params = {
            'owner_name': user.name,
            'shop_name': shop.name,
            'reason': reason,
        }
        
        subject = template.render_subject(**params)
        html_content = template.render_body(**params)
        
        return cls.send_email(user.email, subject, html_content)
