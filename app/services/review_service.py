# app/services/review_service.py
"""口コミ評価サービス"""

from datetime import datetime
from ..extensions import db
from ..models.review import ShopReview, PhoneVerification, ShopReviewScore
from ..models.customer import Customer


class ReviewService:
    """口コミ評価サービス"""
    
    @classmethod
    def submit_review(cls, shop_id, rating, phone_number, customer_id=None,
                      device_fingerprint=None, ip_address=None, user_agent=None):
        """
        口コミを投稿（SMS認証待ち状態で作成）
        
        Returns:
            dict: {'success': bool, 'review': ShopReview or None, 'verification': PhoneVerification or None, 'error': str or None}
        """
        # 口コミ作成
        review, error = ShopReview.create_review(
            shop_id=shop_id,
            rating=rating,
            phone_number=phone_number,
            customer_id=customer_id,
            device_fingerprint=device_fingerprint,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        if error:
            return {'success': False, 'review': None, 'verification': None, 'error': error}
        
        # SMS認証コード作成
        verification, ver_error = PhoneVerification.create_verification(
            phone_number=phone_number,
            purpose='review',
            target_id=review.id,
            ip_address=ip_address
        )
        
        if ver_error:
            db.session.rollback()
            return {'success': False, 'review': None, 'verification': None, 'error': ver_error}
        
        db.session.commit()
        
        return {
            'success': True,
            'review': review,
            'verification': verification,
            'error': None
        }
    
    @classmethod
    def verify_and_complete(cls, review_id, verification_code, customer_id=None):
        """
        SMS認証コードを検証し、口コミを完了
        
        Returns:
            dict: {'success': bool, 'review': ShopReview or None, 'points_rewarded': int, 'error': str or None}
        """
        review = ShopReview.query.get(review_id)
        if not review:
            return {'success': False, 'review': None, 'points_rewarded': 0, 'error': '口コミが見つかりません'}
        
        if review.status != ShopReview.STATUS_PENDING:
            return {'success': False, 'review': review, 'points_rewarded': 0, 'error': 'この口コミは既に処理済みです'}
        
        # 認証コードを検証
        verification = PhoneVerification.get_pending(review.phone_number, 'review')
        if not verification:
            return {'success': False, 'review': review, 'points_rewarded': 0, 'error': '認証コードが見つかりません。再送信してください。'}
        
        success, error = verification.verify(verification_code)
        if not success:
            db.session.commit()  # 試行回数の更新を保存
            return {'success': False, 'review': review, 'points_rewarded': 0, 'error': error}
        
        # 口コミを認証済みに
        review.verify()
        
        # ポイントカード自動発行（顧客がログインしていて、店舗が有料プランの場合）
        card_issued = False
        if customer_id:
            from ..models.shop_point import CustomerShopPoint, ShopPointCard
            from ..models.store_plan import StorePlan
            # 店舗が有料プラン（ポイントカード機能あり）か確認
            plan = StorePlan.query.filter_by(shop_id=review.shop_id).first()
            has_point_card_feature = (
                plan and plan.is_active and 
                plan.plan_type in [StorePlan.PLAN_PREMIUM, StorePlan.PLAN_BUSINESS, 'standard']
            )
            if has_point_card_feature:
                card_config = ShopPointCard.get_or_create(review.shop_id)
                if card_config.is_active:
                    # 顧客のポイントカードを取得（なければ自動発行）
                    customer_point = CustomerShopPoint.get_or_create(customer_id, review.shop_id)
                    card_issued = True
        
        db.session.commit()
        
        # 店舗の口コミスコアを更新
        cls.update_shop_review_score(review.shop_id)
        
        return {
            'success': True,
            'review': review,
            'points_rewarded': 0,
            'card_issued': card_issued,
            'error': None
        }
    
    @classmethod
    def resend_verification_code(cls, review_id, ip_address=None):
        """
        認証コードを再送信
        
        Returns:
            dict: {'success': bool, 'verification': PhoneVerification or None, 'error': str or None}
        """
        review = ShopReview.query.get(review_id)
        if not review:
            return {'success': False, 'verification': None, 'error': '口コミが見つかりません'}
        
        if review.status != ShopReview.STATUS_PENDING:
            return {'success': False, 'verification': None, 'error': 'この口コミは既に処理済みです'}
        
        verification, error = PhoneVerification.create_verification(
            phone_number=review.phone_number,
            purpose='review',
            target_id=review.id,
            ip_address=ip_address
        )
        
        if error:
            return {'success': False, 'verification': None, 'error': error}
        
        db.session.commit()
        
        return {
            'success': True,
            'verification': verification,
            'error': None
        }
    
    @classmethod
    def update_shop_review_score(cls, shop_id):
        """店舗の現在月の口コミスコアを更新"""
        today = datetime.utcnow()
        ShopReviewScore.calculate_for_shop(shop_id, today.year, today.month)
        db.session.commit()
    
    @classmethod
    def get_shop_rating_summary(cls, shop_id):
        """店舗の評価サマリーを取得"""
        return ShopReview.get_shop_rating(shop_id)
    
    @classmethod
    def get_recent_reviews(cls, shop_id, limit=10):
        """店舗の最近の口コミを取得"""
        return ShopReview.get_recent_reviews(shop_id, limit)
    
    @classmethod
    def send_sms_verification(cls, phone_number, code):
        """
        SMS認証コードを送信
        
        Note: 実際のSMS送信はTwilioなどを使用
        """
        from flask import current_app
        
        # Twilio経由でSMS送信（本番用）
        try:
            from ..services.twilio_service import TwilioService
            
            message = f'【Night-Walk】認証コード: {code}\n10分以内に入力してください。'
            TwilioService.send_sms(phone_number, message)
            
            current_app.logger.info(f"SMS verification sent to {phone_number[:3]}***")
            return True
        except Exception as e:
            current_app.logger.error(f"SMS send error: {str(e)}")
            
            # 開発環境ではログ出力のみ
            if current_app.debug:
                current_app.logger.warning(f"[DEV] SMS code for {phone_number}: {code}")
                return True
            
            return False
