# app/jobs/booking_job.py
"""予約関連ジョブ - 遅刻自動キャンセル等"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def process_late_cancellations():
    """
    遅刻キャンセル処理（10分超過した予約を自動キャンセル）
    
    実行頻度: 1分毎
    
    処理内容:
    - 予約時刻から10分経過した「来店待ち」予約を検索
    - 自動的に「遅刻キャンセル」ステータスに変更
    """
    from ..extensions import db
    from ..models.booking import BookingLog
    
    logger.info("Starting late cancellation check...")
    start_time = datetime.utcnow()
    
    try:
        # 遅刻している予約を取得
        late_bookings = BookingLog.get_late_bookings()
        
        if not late_bookings:
            logger.info("No late bookings found.")
            return 0
        
        cancelled_count = 0
        for booking in late_bookings:
            booking.mark_no_show()
            cancelled_count += 1
            logger.info(
                f"Auto-cancelled booking: id={booking.id}, "
                f"shop={booking.shop_id}, "
                f"scheduled={booking.scheduled_at}, "
                f"cast={booking.cast_id}"
            )
        
        db.session.commit()
        
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"Late cancellation completed: {cancelled_count} bookings cancelled in {elapsed:.2f}s")
        
        return cancelled_count
        
    except Exception as e:
        logger.error(f"Error in late cancellation: {e}", exc_info=True)
        db.session.rollback()
        raise


def cleanup_old_bookings(days=90):
    """
    古い予約ログのクリーンアップ
    
    実行頻度: 日次
    
    処理内容:
    - 指定日数以上前の完了・キャンセル済み予約を削除（オプション）
    
    Note: 現在は削除せず、カウントのみ出力
    """
    from datetime import timedelta
    from ..models.booking import BookingLog
    
    logger.info(f"Checking old bookings (older than {days} days)...")
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    old_count = BookingLog.query.filter(
        BookingLog.created_at < cutoff,
        BookingLog.status.in_([
            BookingLog.STATUS_COMPLETED,
            BookingLog.STATUS_CANCELLED,
            BookingLog.STATUS_NO_SHOW
        ])
    ).count()
    
    logger.info(f"Found {old_count} old bookings (not deleted, keeping for audit)")
    
    return old_count


def send_booking_reminders():
    """
    予約リマインダー送信
    
    実行頻度: 5分毎
    
    処理内容:
    - 予約時刻15分前の予約にSMSリマインダー送信
    
    Note: SMS送信にはTwilio設定が必要
    """
    from datetime import timedelta
    from ..models.booking import BookingLog
    
    logger.info("Checking for booking reminders...")
    
    now = datetime.utcnow()
    reminder_window_start = now + timedelta(minutes=14)
    reminder_window_end = now + timedelta(minutes=16)
    
    # 15分前の予約を検索
    upcoming = BookingLog.query.filter(
        BookingLog.status.in_([BookingLog.STATUS_PENDING, BookingLog.STATUS_CONFIRMED]),
        BookingLog.scheduled_at.between(reminder_window_start, reminder_window_end)
    ).all()
    
    if not upcoming:
        logger.info("No upcoming bookings for reminder.")
        return 0
    
    sent_count = 0
    for booking in upcoming:
        # TODO: SMS送信実装
        # TwilioService.send_sms(
        #     booking.customer_phone,
        #     f"【Night-Walk】{booking.shop.name}への予約は{booking.scheduled_at.strftime('%H:%M')}です。"
        # )
        logger.info(
            f"Reminder would be sent: booking={booking.id}, "
            f"phone={booking.customer_phone[:3]}***, "
            f"scheduled={booking.scheduled_at}"
        )
        sent_count += 1
    
    logger.info(f"Reminders processed: {sent_count}")
    return sent_count
