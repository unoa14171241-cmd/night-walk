"""
Night-Walk MVP - Webhook Routes (Stripe, Twilio)
"""
import json
from flask import Blueprint, request, current_app, Response
from ..extensions import db, csrf
from ..models.shop import Shop
from ..models.booking import Call, BookingLog
from ..models.billing import Subscription, BillingEvent
from ..models.audit import AuditLog
from ..utils.logger import audit_log

webhook_bp = Blueprint('webhook', __name__)


@webhook_bp.route('/stripe', methods=['POST'])
@csrf.exempt
def stripe_webhook():
    """Handle Stripe webhook events."""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    
    # Verify signature (in production)
    stripe_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')
    
    if stripe_secret:
        try:
            import stripe
            stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
            event = stripe.Webhook.construct_event(
                payload, sig_header, stripe_secret
            )
        except ValueError as e:
            current_app.logger.error(f"Stripe webhook invalid payload: {e}")
            return Response(status=400)
        except stripe.error.SignatureVerificationError as e:
            current_app.logger.error(f"Stripe webhook signature verification failed: {e}")
            return Response(status=400)
    else:
        # Development mode - parse without verification
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            return Response(status=400)
    
    event_type = event.get('type', '')
    event_id = event.get('id', '')
    data = event.get('data', {}).get('object', {})
    
    current_app.logger.info(f"Stripe webhook received: {event_type}")
    
    try:
        if event_type == 'customer.subscription.created':
            handle_subscription_created(data, event_id, payload)
        
        elif event_type == 'customer.subscription.updated':
            handle_subscription_updated(data, event_id, payload)
        
        elif event_type == 'customer.subscription.deleted':
            handle_subscription_deleted(data, event_id, payload)
        
        elif event_type == 'invoice.paid':
            handle_invoice_paid(data, event_id, payload)
        
        elif event_type == 'invoice.payment_failed':
            handle_invoice_payment_failed(data, event_id, payload)
        
        db.session.commit()
        
    except Exception as e:
        current_app.logger.error(f"Stripe webhook error: {e}")
        db.session.rollback()
        return Response(status=500)
    
    return Response(status=200)


def handle_subscription_created(data, event_id, payload):
    """Handle subscription created event."""
    stripe_subscription_id = data.get('id')
    stripe_customer_id = data.get('customer')
    status = data.get('status')
    
    subscription = Subscription.query.filter_by(
        stripe_subscription_id=stripe_subscription_id
    ).first()
    
    if subscription:
        subscription.status = map_stripe_status(status)
        
        # Log billing event
        log_billing_event(subscription.shop_id, 'subscription.created', event_id, payload)


def handle_subscription_updated(data, event_id, payload):
    """Handle subscription updated event."""
    stripe_subscription_id = data.get('id')
    status = data.get('status')
    
    subscription = Subscription.query.filter_by(
        stripe_subscription_id=stripe_subscription_id
    ).first()
    
    if subscription:
        old_status = subscription.status
        subscription.status = map_stripe_status(status)
        
        # Update shop active status based on subscription
        if subscription.status in ['canceled', 'unpaid']:
            subscription.shop.is_published = False
        
        log_billing_event(subscription.shop_id, 'subscription.updated', event_id, payload)
        
        audit_log(AuditLog.ACTION_BILLING_EVENT, 'subscription', subscription.id,
                 old_value={'status': old_status},
                 new_value={'status': subscription.status})


def handle_subscription_deleted(data, event_id, payload):
    """Handle subscription deleted event."""
    from ..models.store_plan import StorePlan
    
    stripe_subscription_id = data.get('id')
    
    # 従来のSubscriptionモデル
    subscription = Subscription.query.filter_by(
        stripe_subscription_id=stripe_subscription_id
    ).first()
    
    if subscription:
        subscription.status = 'canceled'
        subscription.shop.is_published = False
        log_billing_event(subscription.shop_id, 'subscription.deleted', event_id, payload)
    
    # StorePlanモデル（新課金システム）
    store_plan = StorePlan.query.filter_by(
        stripe_subscription_id=stripe_subscription_id
    ).first()
    
    if store_plan:
        store_plan.plan_type = StorePlan.PLAN_FREE
        store_plan.status = StorePlan.STATUS_ACTIVE
        store_plan.stripe_subscription_id = None
        # 広告権利を同期（無料プランの特典のみに）
        store_plan.sync_entitlements()
        
        log_billing_event(store_plan.shop_id, 'store_plan.subscription.deleted', event_id, payload)


def handle_invoice_paid(data, event_id, payload):
    """Handle invoice paid event."""
    from ..models.store_plan import StorePlan
    
    subscription_id = data.get('subscription')
    amount = data.get('amount_paid', 0)
    
    # 従来のSubscriptionモデル
    subscription = Subscription.query.filter_by(
        stripe_subscription_id=subscription_id
    ).first()
    
    if subscription:
        subscription.status = 'active'
        log_billing_event(subscription.shop_id, 'invoice.paid', event_id, payload, amount)
    
    # StorePlanモデル（新課金システム）
    store_plan = StorePlan.query.filter_by(
        stripe_subscription_id=subscription_id
    ).first()
    
    if store_plan:
        store_plan.status = StorePlan.STATUS_ACTIVE
        # 広告権利を同期
        store_plan.sync_entitlements()
        
        log_billing_event(store_plan.shop_id, 'store_plan.invoice.paid', event_id, payload, amount)


def handle_invoice_payment_failed(data, event_id, payload):
    """Handle invoice payment failed event."""
    subscription_id = data.get('subscription')
    amount = data.get('amount_due', 0)
    
    subscription = Subscription.query.filter_by(
        stripe_subscription_id=subscription_id
    ).first()
    
    if subscription:
        subscription.status = 'past_due'
        
        log_billing_event(subscription.shop_id, 'invoice.payment_failed', event_id, payload, amount)


def map_stripe_status(stripe_status):
    """Map Stripe subscription status to our status."""
    mapping = {
        'trialing': 'trial',
        'active': 'active',
        'past_due': 'past_due',
        'canceled': 'canceled',
        'unpaid': 'unpaid',
    }
    return mapping.get(stripe_status, stripe_status)


def log_billing_event(shop_id, event_type, event_id, payload, amount=None):
    """Log a billing event."""
    event = BillingEvent(
        shop_id=shop_id,
        event_type=event_type,
        stripe_event_id=event_id,
        amount=amount,
        payload=payload if isinstance(payload, str) else json.dumps(payload)
    )
    db.session.add(event)


# ============================================
# Twilio Webhooks
# ============================================

def validate_twilio_request():
    """Validate that the request is from Twilio."""
    auth_token = current_app.config.get('TWILIO_AUTH_TOKEN')
    
    if not auth_token:
        # Development mode - skip validation
        current_app.logger.warning("Twilio auth token not configured, skipping validation")
        return True
    
    from twilio.request_validator import RequestValidator
    
    validator = RequestValidator(auth_token)
    
    # Get the full URL including query string
    url = request.url
    
    # Get the POST parameters
    post_vars = request.form.to_dict()
    
    # Get the signature header
    signature = request.headers.get('X-Twilio-Signature', '')
    
    is_valid = validator.validate(url, post_vars, signature)
    
    if not is_valid:
        current_app.logger.warning(f"Invalid Twilio signature for URL: {url}")
    
    return is_valid


@webhook_bp.route('/twilio/voice', methods=['POST'])
@csrf.exempt
def twilio_voice():
    """Handle incoming Twilio voice callback."""
    try:
        from twilio.twiml.voice_response import VoiceResponse
    except ImportError:
        current_app.logger.error("twilio package not installed")
        return Response("Service unavailable", status=503)
    
    # Validate Twilio signature
    if not validate_twilio_request():
        current_app.logger.error("Twilio request validation failed")
        return Response("Forbidden", status=403)
    
    call_sid = request.form.get('CallSid')
    from_number = request.form.get('From')
    digits = request.form.get('Digits')
    shop_id = request.args.get('shop_id')
    
    current_app.logger.info(f"Twilio voice callback: {call_sid}, shop={shop_id}, digits={digits}")
    
    response = VoiceResponse()
    
    if not shop_id:
        response.say("エラーが発生しました。", language='ja-JP')
        response.hangup()
        return Response(str(response), mimetype='text/xml')
    
    shop = Shop.query.get(shop_id)
    if not shop:
        response.say("店舗が見つかりませんでした。", language='ja-JP')
        response.hangup()
        return Response(str(response), mimetype='text/xml')
    
    # Find existing booking linked to this call
    call_record = Call.query.filter_by(call_sid=call_sid).first()
    existing_booking = None
    if call_record:
        existing_booking = BookingLog.query.filter_by(call_id=call_record.id).first()
    
    # If digits pressed, process reservation
    if digits:
        if call_record:
            call_record.digits_pressed = digits
        
        if digits == '1':
            # Confirm reservation - update existing booking (don't create a new one)
            if existing_booking:
                existing_booking.status = BookingLog.STATUS_CONFIRMED
                db.session.commit()
                
                # Build confirmation message with booking details
                cast_info = ''
                if existing_booking.is_free_nomination:
                    cast_info = '、指名はフリーです'
                elif existing_booking.cast:
                    cast_info = f'、指名は{existing_booking.cast.name_display}さんです'
                
                time_info = ''
                if existing_booking.scheduled_at:
                    time_info = f'、来店予定は{existing_booking.scheduled_at.strftime("%H時%M分")}です'
                
                party_info = f'、{existing_booking.party_size}名様でのご来店です' if existing_booking.party_size else ''
                
                response.say(
                    f"{shop.name}への予約を承りました{time_info}{party_info}{cast_info}。"
                    f"予約時刻までにお越しください。",
                    language='ja-JP'
                )
                
                audit_log(AuditLog.ACTION_BOOKING_CREATE, 'shop', shop.id,
                         new_value={'type': 'phone', 'status': 'confirmed',
                                    'booking_id': existing_booking.id})
                
                # Notify shop about the new booking via phone call
                try:
                    from ..services.twilio_service import notify_shop_booking
                    notify_shop_booking(existing_booking.id)
                except Exception as e:
                    current_app.logger.error(f"Shop notification failed: {e}")
            else:
                # Fallback: no existing booking found (shouldn't happen with new flow)
                response.say(f"{shop.name}への予約を承りました。店舗からのご連絡をお待ちください。", language='ja-JP')
                current_app.logger.warning(f"No existing booking found for call_sid={call_sid}")
        
        elif digits == '2':
            # Cancel reservation
            if existing_booking and existing_booking.can_cancel:
                existing_booking.cancel(reason='ユーザーが通話中にキャンセル')
                db.session.commit()
            response.say("予約をキャンセルしました。", language='ja-JP')
        else:
            response.say("無効な入力です。予約をキャンセルしました。", language='ja-JP')
        
        response.hangup()
    else:
        # Initial call - provide menu with booking details
        booking_detail = ""
        if existing_booking:
            time_part = ""
            if existing_booking.scheduled_at:
                time_part = f"来店時間は{existing_booking.scheduled_at.strftime('%H時%M分')}、"
            
            party_part = f"{existing_booking.party_size}名様、" if existing_booking.party_size else ""
            
            cast_part = ""
            if existing_booking.is_free_nomination:
                cast_part = "指名はフリーです。"
            elif existing_booking.cast:
                cast_part = f"指名は{existing_booking.cast.name_display}さんです。"
            
            booking_detail = f"{time_part}{party_part}{cast_part}"
        
        response.say(
            f"こちらは{shop.name}の予約受付です。{booking_detail}",
            language='ja-JP'
        )
        
        gather = response.gather(
            num_digits=1,
            action=f'/webhook/twilio/voice?shop_id={shop_id}',
            method='POST',
            timeout=10
        )
        gather.say(
            "予約を確定する場合は1を、キャンセルは2を押してください。",
            language='ja-JP'
        )
        
        response.say("入力がありませんでした。電話を終了します。", language='ja-JP')
        response.hangup()
    
    return Response(str(response), mimetype='text/xml')


@webhook_bp.route('/twilio/status', methods=['POST'])
@csrf.exempt
def twilio_status():
    """Handle Twilio call status callback."""
    # Validate Twilio signature
    if not validate_twilio_request():
        current_app.logger.error("Twilio status request validation failed")
        return Response("Forbidden", status=403)
    
    call_sid = request.form.get('CallSid')
    call_status = request.form.get('CallStatus')
    duration = request.form.get('CallDuration')
    
    current_app.logger.info(f"Twilio status callback: {call_sid}, status={call_status}")
    
    call = Call.query.filter_by(call_sid=call_sid).first()
    if call:
        call.status = call_status
        if duration:
            call.duration = int(duration)
        if call_status in ['completed', 'failed', 'no-answer', 'busy']:
            from datetime import datetime
            call.ended_at = datetime.utcnow()
        
        db.session.commit()
    
    return Response(status=200)


@webhook_bp.route('/twilio/shop-notify', methods=['POST'])
@csrf.exempt
def twilio_shop_notify():
    """
    Handle Twilio voice callback for shop notification.
    Reads booking details to the shop staff (or leaves a voicemail).
    """
    try:
        from twilio.twiml.voice_response import VoiceResponse
    except ImportError:
        current_app.logger.error("twilio package not installed")
        return Response("Service unavailable", status=503)
    
    # Validate Twilio signature
    if not validate_twilio_request():
        current_app.logger.error("Twilio shop notify request validation failed")
        return Response("Forbidden", status=403)
    
    booking_id = request.args.get('booking_id')
    
    response = VoiceResponse()
    
    if not booking_id:
        response.say("エラーが発生しました。", language='ja-JP')
        response.hangup()
        return Response(str(response), mimetype='text/xml')
    
    booking = BookingLog.query.get(booking_id)
    if not booking:
        response.say("予約情報が見つかりませんでした。", language='ja-JP')
        response.hangup()
        return Response(str(response), mimetype='text/xml')
    
    shop = Shop.query.get(booking.shop_id)
    shop_name = shop.name if shop else '店舗'
    
    # Build notification message
    message_parts = [f"ナイトウォークからの予約通知です。{shop_name}に新しい予約が入りました。"]
    
    # Time info
    if booking.scheduled_at:
        message_parts.append(
            f"来店予定時刻は{booking.scheduled_at.strftime('%H時%M分')}です。"
        )
    
    # Party size
    if booking.party_size:
        message_parts.append(f"人数は{booking.party_size}名様です。")
    
    # Cast nomination
    if booking.is_free_nomination:
        message_parts.append("指名はフリーです。")
    elif booking.cast:
        message_parts.append(f"指名キャストは{booking.cast.name_display}さんです。")
    
    # Customer phone
    if booking.customer_phone:
        # Read phone number digit by digit for clarity
        phone_display = booking.customer_phone[-4:]  # Last 4 digits only for privacy
        message_parts.append(f"お客様の電話番号の下4桁は{phone_display}です。")
    
    message_parts.append("予約管理画面でご確認ください。")
    message_parts.append("繰り返します。")
    
    full_message = "".join(message_parts)
    
    # Say the message twice (in case they pick up late or voicemail starts late)
    response.pause(length=1)
    response.say(full_message, language='ja-JP')
    response.pause(length=1)
    response.say(full_message, language='ja-JP')
    response.hangup()
    
    current_app.logger.info(f"Shop notification delivered for booking #{booking_id}")
    
    return Response(str(response), mimetype='text/xml')
