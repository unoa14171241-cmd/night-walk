# app/services/booking_service.py
"""予約サービス - 直前限定予約（30〜60分）＋指名キャスト必須"""

from datetime import datetime, timedelta
from flask import current_app
from ..extensions import db
from ..models.booking import BookingLog, Call
from ..models.shop import Shop
from ..models.gift import Cast
from ..models.customer import Customer


class BookingService:
    """予約サービス"""
    
    @classmethod
    def create_booking(cls, shop_id, cast_id, scheduled_at, 
                       customer_id=None, customer_phone=None, customer_name=None,
                       party_size=1, notes=None, booking_type='web'):
        """
        予約を作成（直前限定：30〜60分後のみ）
        
        Args:
            shop_id: 店舗ID
            cast_id: 指名キャストID（必須）
            scheduled_at: 予約時刻
            customer_id: 顧客ID（ログインユーザー）
            customer_phone: 電話番号
            customer_name: 予約者名
            party_size: 人数
            notes: 備考
            booking_type: 予約タイプ (web/phone)
        
        Returns:
            dict: {'success': bool, 'booking': BookingLog or None, 'error': str or None}
        """
        # 店舗チェック
        shop = Shop.query.get(shop_id)
        if not shop or not shop.is_active or not shop.is_published:
            return {'success': False, 'booking': None, 'error': '店舗が見つかりません'}
        
        # キャストチェック（必須）
        if not cast_id:
            return {'success': False, 'booking': None, 'error': '指名キャストを選択してください'}
        
        cast = Cast.query.get(cast_id)
        if not cast or not cast.is_active or cast.shop_id != shop_id:
            return {'success': False, 'booking': None, 'error': '指定されたキャストは選択できません'}
        
        # 予約時刻バリデーション（30〜60分後のみ）
        is_valid, error = BookingLog.validate_scheduled_time(scheduled_at)
        if not is_valid:
            return {'success': False, 'booking': None, 'error': error}
        
        # 電話番号必須チェック
        if not customer_phone:
            return {'success': False, 'booking': None, 'error': '電話番号を入力してください'}
        
        # 重複予約チェック（同じ顧客が同じ店舗に来店待ちの予約がある場合）
        existing = BookingLog.query.filter(
            BookingLog.shop_id == shop_id,
            BookingLog.customer_phone == customer_phone,
            BookingLog.status.in_([BookingLog.STATUS_PENDING, BookingLog.STATUS_CONFIRMED])
        ).first()
        
        if existing:
            return {'success': False, 'booking': None, 'error': 'この店舗に既に予約があります'}
        
        # 予約作成
        booking = BookingLog(
            shop_id=shop_id,
            cast_id=cast_id,
            customer_id=customer_id,
            customer_phone=customer_phone,
            customer_name=customer_name,
            party_size=party_size,
            scheduled_at=scheduled_at,
            booking_type=booking_type,
            status=BookingLog.STATUS_CONFIRMED,
            notes=notes
        )
        
        db.session.add(booking)
        db.session.commit()
        
        current_app.logger.info(
            f"Booking created: shop={shop_id}, cast={cast_id}, "
            f"scheduled={scheduled_at}, phone={customer_phone[:3]}***"
        )
        
        return {'success': True, 'booking': booking, 'error': None}
    
    @classmethod
    def cancel_booking(cls, booking_id, reason=None, user_id=None):
        """
        予約をキャンセル
        
        Args:
            booking_id: 予約ID
            reason: キャンセル理由
            user_id: キャンセル実行者ID
        
        Returns:
            dict: {'success': bool, 'error': str or None}
        """
        booking = BookingLog.query.get(booking_id)
        if not booking:
            return {'success': False, 'error': '予約が見つかりません'}
        
        if not booking.can_cancel:
            return {'success': False, 'error': 'この予約はキャンセルできません'}
        
        booking.cancel(reason)
        db.session.commit()
        
        current_app.logger.info(f"Booking cancelled: id={booking_id}, reason={reason}")
        
        return {'success': True, 'error': None}
    
    @classmethod
    def complete_booking(cls, booking_id):
        """
        来店完了
        
        Args:
            booking_id: 予約ID
        
        Returns:
            dict: {'success': bool, 'error': str or None}
        """
        booking = BookingLog.query.get(booking_id)
        if not booking:
            return {'success': False, 'error': '予約が見つかりません'}
        
        if booking.status not in [BookingLog.STATUS_PENDING, BookingLog.STATUS_CONFIRMED]:
            return {'success': False, 'error': 'この予約は完了処理できません'}
        
        booking.complete()
        db.session.commit()
        
        current_app.logger.info(f"Booking completed: id={booking_id}")
        
        return {'success': True, 'error': None}
    
    @classmethod
    def process_late_cancellations(cls):
        """
        遅刻キャンセル処理（10分超過した予約を自動キャンセル）
        スケジューラから呼び出される
        
        Returns:
            int: キャンセルした予約数
        """
        late_bookings = BookingLog.get_late_bookings()
        cancelled_count = 0
        
        for booking in late_bookings:
            booking.mark_no_show()
            cancelled_count += 1
            current_app.logger.info(
                f"Auto-cancelled late booking: id={booking.id}, "
                f"scheduled={booking.scheduled_at}"
            )
        
        if cancelled_count > 0:
            db.session.commit()
        
        return cancelled_count
    
    @classmethod
    def get_shop_bookings(cls, shop_id, status=None, date=None):
        """
        店舗の予約一覧を取得
        
        Args:
            shop_id: 店舗ID
            status: ステータスフィルタ
            date: 日付フィルタ
        
        Returns:
            list: BookingLog objects
        """
        query = BookingLog.query.filter_by(shop_id=shop_id)
        
        if status:
            query = query.filter_by(status=status)
        
        if date:
            start = datetime.combine(date, datetime.min.time())
            end = datetime.combine(date, datetime.max.time())
            query = query.filter(BookingLog.scheduled_at.between(start, end))
        
        return query.order_by(BookingLog.scheduled_at.desc()).all()
    
    @classmethod
    def get_customer_bookings(cls, customer_id=None, customer_phone=None, limit=20):
        """
        顧客の予約履歴を取得
        
        Args:
            customer_id: 顧客ID
            customer_phone: 電話番号
            limit: 取得件数
        
        Returns:
            list: BookingLog objects
        """
        query = BookingLog.query
        
        if customer_id:
            query = query.filter_by(customer_id=customer_id)
        elif customer_phone:
            query = query.filter_by(customer_phone=customer_phone)
        else:
            return []
        
        return query.order_by(BookingLog.created_at.desc()).limit(limit).all()
    
    @classmethod
    def get_available_casts(cls, shop_id):
        """
        予約可能なキャスト一覧を取得
        
        Args:
            shop_id: 店舗ID
        
        Returns:
            list: Cast objects (出勤中のキャストを優先)
        """
        # 全アクティブキャスト
        casts = Cast.query.filter_by(
            shop_id=shop_id,
            is_active=True,
            is_visible=True
        ).order_by(
            # 出勤中を優先
            Cast.work_status.desc(),
            Cast.sort_order,
            Cast.name
        ).all()
        
        return casts
