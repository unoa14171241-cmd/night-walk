"""
Night-Walk MVP - Twilio Service
Handles phone reservation automation and SMS verification
"""
from datetime import datetime
from flask import current_app, url_for
from ..extensions import db
from ..models.shop import Shop
from ..models.booking import Call, BookingLog


class TwilioService:
    """Twilio SMS/Voice service wrapper"""

    @classmethod
    def send_sms(cls, to_number, message):
        """
        Send an SMS message via Twilio.

        Args:
            to_number: Destination phone number (E.164 format)
            message: SMS body text

        Returns:
            bool: True if sent successfully
        """
        account_sid = current_app.config.get('TWILIO_ACCOUNT_SID')
        auth_token = current_app.config.get('TWILIO_AUTH_TOKEN')
        from_number = current_app.config.get('TWILIO_PHONE_NUMBER')

        if not all([account_sid, auth_token, from_number]):
            current_app.logger.warning("Twilio is not configured - SMS not sent")
            if current_app.debug:
                current_app.logger.info(f"[DEV] SMS to {to_number}: {message}")
                return True
            return False

        try:
            from twilio.rest import Client

            client = Client(account_sid, auth_token)
            client.messages.create(
                to=to_number,
                from_=from_number,
                body=message
            )
            current_app.logger.info(f"SMS sent to {to_number[:5]}***")
            return True
        except Exception as e:
            current_app.logger.error(f"Twilio SMS error: {e}")
            if current_app.debug:
                current_app.logger.info(f"[DEV] SMS to {to_number}: {message}")
                return True
            return False


def initiate_call(shop_id, caller_phone):
    """
    Initiate an automated phone call for reservation.
    
    Args:
        shop_id: Shop ID
        caller_phone: Caller's phone number (E.164 format)
    
    Returns:
        dict with call info or error
    """
    # Check Twilio configuration
    account_sid = current_app.config.get('TWILIO_ACCOUNT_SID')
    auth_token = current_app.config.get('TWILIO_AUTH_TOKEN')
    from_number = current_app.config.get('TWILIO_PHONE_NUMBER')
    
    if not all([account_sid, auth_token, from_number]):
        return {
            'success': False,
            'error': 'Twilio is not configured'
        }
    
    # Get shop
    shop = Shop.query.get(shop_id)
    if not shop:
        return {
            'success': False,
            'error': 'Shop not found'
        }
    
    if not shop.phone:
        return {
            'success': False,
            'error': 'Shop has no phone number'
        }
    
    try:
        from twilio.rest import Client
        
        client = Client(account_sid, auth_token)
        
        # Create TwiML URL for voice callback
        voice_url = url_for('webhook.twilio_voice', shop_id=shop_id, _external=True)
        status_url = url_for('webhook.twilio_status', _external=True)
        
        # Initiate call
        call = client.calls.create(
            to=caller_phone,
            from_=from_number,
            url=voice_url,
            status_callback=status_url,
            status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
        )
        
        # Log call
        call_log = Call(
            shop_id=shop_id,
            call_sid=call.sid,
            caller_number=caller_phone,
            status='initiated',
        )
        db.session.add(call_log)
        db.session.commit()
        
        return {
            'success': True,
            'call_sid': call.sid,
            'status': 'initiated'
        }
        
    except Exception as e:
        current_app.logger.error(f"Twilio call error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def get_call_status(call_sid):
    """
    Get the status of a call.
    
    Args:
        call_sid: Twilio Call SID
    
    Returns:
        dict with call status
    """
    call = Call.query.filter_by(call_sid=call_sid).first()
    
    if not call:
        return {
            'found': False,
            'error': 'Call not found'
        }
    
    return {
        'found': True,
        'call_sid': call.call_sid,
        'status': call.status,
        'duration': call.duration,
        'digits_pressed': call.digits_pressed,
        'started_at': call.started_at.isoformat() if call.started_at else None,
        'ended_at': call.ended_at.isoformat() if call.ended_at else None,
    }


def create_booking_from_call(call_id, shop_id, status='confirmed', notes=None):
    """
    Create a booking log from a completed call.
    
    Args:
        call_id: Call ID
        shop_id: Shop ID
        status: Booking status ('confirmed', 'cancelled', 'no_answer')
        notes: Optional notes
    
    Returns:
        BookingLog object or None
    """
    try:
        booking = BookingLog(
            call_id=call_id,
            shop_id=shop_id,
            booking_type='phone',
            status=status,
            notes=notes
        )
        db.session.add(booking)
        db.session.commit()
        
        return booking
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Booking creation error: {e}")
        return None
