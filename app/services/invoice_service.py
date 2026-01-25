"""
Night-Walk - Invoice Service (Render Compatible)
PDF generation with xhtml2pdf, email sending via SendGrid
"""
import io
import base64
from datetime import datetime
from flask import current_app, render_template


class InvoiceService:
    """Service for generating and sending invoices."""
    
    # Company information - can be overridden via config
    COMPANY_INFO = {
        'name': 'Night-Walk運営事務局',
        'postal_code': '700-0000',
        'address': '岡山県岡山市北区XX町1-2-3',
        'phone': '086-XXX-XXXX',
        'email': 'billing@night-walk.jp',
        'bank_name': 'XXX銀行 YYY支店',
        'bank_account_type': '普通',
        'bank_account_number': '1234567',
        'bank_account_holder': 'ナイトウォーク（カ',
    }
    
    @classmethod
    def get_company_info(cls):
        """Get company info from config or defaults."""
        return current_app.config.get('COMPANY_INFO', cls.COMPANY_INFO)
    
    @classmethod
    def generate_pdf(cls, billing):
        """
        Generate invoice PDF in memory.
        
        Args:
            billing: MonthlyBilling instance
            
        Returns:
            bytes: PDF file content
        """
        from xhtml2pdf import pisa
        from ..models.commission import Commission
        
        # Generate invoice number if not exists
        if not billing.invoice_number:
            billing.generate_invoice_number()
        
        # Get commission details
        commissions = billing.commissions.filter(
            Commission.status.in_([Commission.STATUS_CONFIRMED, Commission.STATUS_PAID])
        ).order_by(Commission.visit_date).all()
        
        # Render HTML template
        html_content = render_template('invoices/invoice.html',
            billing=billing,
            shop=billing.shop,
            commissions=commissions,
            company=cls.get_company_info(),
            generated_at=datetime.now()
        )
        
        # Convert HTML to PDF in memory
        pdf_buffer = io.BytesIO()
        
        # xhtml2pdf conversion
        pisa_status = pisa.CreatePDF(
            src=html_content,
            dest=pdf_buffer,
            encoding='utf-8'
        )
        
        if pisa_status.err:
            current_app.logger.error(f"PDF generation error: {pisa_status.err}")
            raise Exception("PDF generation failed")
        
        pdf_buffer.seek(0)
        return pdf_buffer.read()
    
    @classmethod
    def send_invoice(cls, billing, recipient_email):
        """
        Send invoice via SendGrid.
        
        Args:
            billing: MonthlyBilling instance
            recipient_email: Email address to send to
            
        Returns:
            bool: Success status
        """
        import sendgrid
        from sendgrid.helpers.mail import (
            Mail, Attachment, FileContent, FileName, FileType, Disposition
        )
        
        api_key = current_app.config.get('SENDGRID_API_KEY')
        
        if not api_key:
            current_app.logger.error("SENDGRID_API_KEY not configured")
            raise Exception("メール設定が完了していません")
        
        # Generate PDF
        try:
            pdf_content = cls.generate_pdf(billing)
        except Exception as e:
            current_app.logger.error(f"PDF generation failed: {e}")
            raise Exception(f"請求書の生成に失敗しました: {e}")
        
        # Create SendGrid client
        sg = sendgrid.SendGridAPIClient(api_key=api_key)
        
        # Email content
        html_body = render_template('emails/invoice.html',
            billing=billing,
            shop=billing.shop,
            company=cls.get_company_info()
        )
        
        sender_email = current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@night-walk.jp')
        
        message = Mail(
            from_email=sender_email,
            to_emails=recipient_email,
            subject=f"【Night-Walk】{billing.period_display} 送客手数料請求書",
            html_content=html_body
        )
        
        # Attach PDF
        encoded_pdf = base64.b64encode(pdf_content).decode()
        attachment = Attachment(
            FileContent(encoded_pdf),
            FileName(f'請求書_{billing.invoice_number}.pdf'),
            FileType('application/pdf'),
            Disposition('attachment')
        )
        message.attachment = attachment
        
        try:
            response = sg.send(message)
            
            if response.status_code in [200, 201, 202]:
                # Update billing record
                billing.sent_at = datetime.utcnow()
                billing.sent_to = recipient_email
                if billing.status in ['open', 'closed']:
                    billing.status = 'invoiced'
                if not billing.invoiced_at:
                    billing.invoiced_at = datetime.utcnow()
                
                current_app.logger.info(f"Invoice sent: {billing.invoice_number} to {recipient_email}")
                return True
            else:
                current_app.logger.error(f"SendGrid error: {response.status_code} - {response.body}")
                return False
                
        except Exception as e:
            current_app.logger.error(f"Failed to send invoice: {e}")
            raise Exception(f"メール送信に失敗しました: {e}")
    
    @classmethod
    def preview_pdf(cls, billing):
        """
        Generate PDF for preview/download.
        
        Args:
            billing: MonthlyBilling instance
            
        Returns:
            bytes: PDF content
        """
        return cls.generate_pdf(billing)
