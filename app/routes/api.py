"""
Night-Walk MVP - Internal API Routes
"""
from datetime import datetime
from flask import Blueprint, jsonify, request, g, session
from flask_login import login_required, current_user
from ..extensions import db, limiter
from ..models.shop import Shop, VacancyStatus, VacancyHistory
from ..models.audit import AuditLog
from ..utils.decorators import shop_access_required
from ..utils.logger import audit_log
from ..utils.helpers import get_client_ip
from ..services.ad_service import AdService
from ..services.trending_service import TrendingService

api_bp = Blueprint('api', __name__)


@api_bp.route('/vacancy/<int:shop_id>', methods=['GET'])
@limiter.limit("60 per minute")
def get_vacancy(shop_id):
    """Get current vacancy status for a shop."""
    shop = Shop.query.filter_by(id=shop_id, is_active=True).first()
    
    if not shop:
        return jsonify({'error': 'Shop not found'}), 404
    
    vacancy = shop.vacancy_status
    
    return jsonify({
        'shop_id': shop_id,
        'status': vacancy.status if vacancy else 'unknown',
        'label': vacancy.label if vacancy else '−',
        'color': vacancy.color if vacancy else 'secondary',
        'updated_at': vacancy.updated_at.isoformat() if vacancy and vacancy.updated_at else None,
    })


@api_bp.route('/vacancy/<int:shop_id>', methods=['POST'])
@limiter.limit("30 per minute")
@login_required
def update_vacancy(shop_id):
    """Update vacancy status for a shop."""
    # Check access
    if not current_user.is_admin and not current_user.can_access_shop(shop_id):
        return jsonify({'error': 'Access denied'}), 403
    
    shop = Shop.query.get_or_404(shop_id)
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    new_status = data.get('status')
    if new_status not in VacancyStatus.STATUSES:
        return jsonify({'error': 'Invalid status'}), 400
    
    # Get or create vacancy status
    vacancy = shop.vacancy_status
    if not vacancy:
        vacancy = VacancyStatus(shop_id=shop.id)
        db.session.add(vacancy)
    
    old_status = vacancy.status
    
    # Update
    vacancy.status = new_status
    vacancy.updated_at = datetime.utcnow()
    vacancy.updated_by = current_user.id
    
    # Record history
    history = VacancyHistory(
        shop_id=shop.id,
        status=new_status,
        changed_by=current_user.id,
        ip_address=get_client_ip()
    )
    db.session.add(history)
    db.session.commit()
    
    # Audit log
    audit_log(AuditLog.ACTION_VACANCY_UPDATE, 'shop', shop.id,
             old_value={'status': old_status},
             new_value={'status': new_status})
    
    return jsonify({
        'success': True,
        'shop_id': shop_id,
        'status': vacancy.status,
        'label': vacancy.label,
        'color': vacancy.color,
        'updated_at': vacancy.updated_at.isoformat(),
    })


@api_bp.route('/shops', methods=['GET'])
@limiter.limit("30 per minute")
def get_shops():
    """Get list of published shops."""
    area = request.args.get('area', '')
    
    query = Shop.query.filter_by(is_published=True, is_active=True)
    
    if area and area in Shop.AREAS:
        query = query.filter_by(area=area)
    
    shops = query.order_by(Shop.name).all()
    
    result = []
    for shop in shops:
        vacancy = shop.vacancy_status
        result.append({
            'id': shop.id,
            'name': shop.name,
            'area': shop.area,
            # 公開APIでは終了時刻を出さない
            'business_hours': shop.public_business_hours,
            'price_range': shop.price_range,
            'image_url': shop.image_url,
            'vacancy': {
                'status': vacancy.status if vacancy else 'unknown',
                'label': vacancy.label if vacancy else '−',
                'color': vacancy.color if vacancy else 'secondary',
                'updated_at': vacancy.updated_at.isoformat() if vacancy and vacancy.updated_at else None,
            }
        })
    
    return jsonify({'shops': result})


@api_bp.route('/stats', methods=['GET'])
@login_required
def get_stats():
    """Get dashboard statistics."""
    if current_user.is_admin:
        # Admin stats
        from ..models.booking import BookingLog
        from datetime import date
        
        today = date.today()
        today_bookings = BookingLog.query.filter(
            db.func.date(BookingLog.created_at) == today
        ).count()
        
        vacancy_stats = db.session.query(
            VacancyStatus.status, db.func.count(VacancyStatus.id)
        ).group_by(VacancyStatus.status).all()
        
        return jsonify({
            'today_bookings': today_bookings,
            'vacancy_stats': dict(vacancy_stats),
        })
    
    # Shop stats
    shop = g.get('current_shop')
    if not shop:
        return jsonify({'error': 'No shop selected'}), 400
    
    from ..models.booking import BookingLog
    from datetime import date
    
    today = date.today()
    today_bookings = BookingLog.query.filter(
        BookingLog.shop_id == shop.id,
        db.func.date(BookingLog.created_at) == today
    ).count()
    
    vacancy = shop.vacancy_status
    
    return jsonify({
        'shop_id': shop.id,
        'today_bookings': today_bookings,
        'vacancy': {
            'status': vacancy.status if vacancy else 'unknown',
            'label': vacancy.label if vacancy else '−',
            'updated_at': vacancy.updated_at.isoformat() if vacancy and vacancy.updated_at else None,
        }
    })


# ============================================
# PV Recording API
# ============================================

@api_bp.route('/pv', methods=['POST'])
@limiter.limit("120 per minute")
def record_pv():
    """
    PVを記録
    
    Request body:
        target_type: 'shop' or 'cast'
        target_id: int
        page_type: 'detail', 'booking', 'job' (optional)
    """
    import uuid
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    target_type = data.get('target_type')
    target_id = data.get('target_id')
    page_type = data.get('page_type', 'detail')
    
    if target_type not in ['shop', 'cast']:
        return jsonify({'error': 'Invalid target_type'}), 400
    
    if not target_id:
        return jsonify({'error': 'target_id is required'}), 400
    
    # ユーザー識別
    customer_id = None
    session_id = None
    
    if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
        if hasattr(current_user, 'is_customer') and current_user.is_customer:
            customer_id = current_user.id
    
    if not customer_id:
        if 'visitor_id' not in session:
            session['visitor_id'] = str(uuid.uuid4())
        session_id = session['visitor_id']
    
    # PV記録
    recorded = False
    if target_type == 'shop':
        recorded = TrendingService.record_shop_view(
            shop_id=target_id,
            customer_id=customer_id,
            session_id=session_id,
            ip_address=get_client_ip(),
            user_agent=request.user_agent.string if request.user_agent else None,
            referrer=request.referrer,
            page_type=page_type
        )
    else:
        from ..services.ranking_service import RankingService
        recorded = RankingService.record_page_view(
            cast_id=target_id,
            customer_id=customer_id,
            session_id=session_id,
            ip_address=get_client_ip(),
            user_agent=request.user_agent.string if request.user_agent else None
        )
    
    if recorded:
        db.session.commit()
    
    return jsonify({
        'success': True,
        'recorded': recorded
    })


# ============================================
# Trending API
# ============================================

@api_bp.route('/trending', methods=['GET'])
@limiter.limit("60 per minute")
def get_trending():
    """
    急上昇データを取得
    
    Query params:
        area: エリア（岡山、倉敷）
        type: 'shop' or 'cast' or 'both' (default: 'both')
        limit: 表示件数 (default: 10)
    """
    area = request.args.get('area', '')
    target_type = request.args.get('type', 'both')
    limit = request.args.get('limit', 10, type=int)
    
    # エリアバリデーション
    if area and area not in Shop.AREAS:
        area = None
    
    result = {}
    
    if target_type in ['shop', 'both']:
        trending_shops = TrendingService.get_trending_shops(area=area, limit=limit)
        result['shops'] = [{
            'rank': t.rank,
            'shop_id': t.shop_id,
            'shop_name': t.shop.name if t.shop else None,
            'area': t.area,
            'current_pv': t.current_pv,
            'previous_pv': t.previous_pv,
            'growth_rate': round(t.growth_rate, 2),
            'image_url': t.shop.main_image_url if t.shop else None,
        } for t in trending_shops]
    
    if target_type in ['cast', 'both']:
        trending_casts = TrendingService.get_trending_casts(area=area, limit=limit)
        result['casts'] = [{
            'rank': t.rank,
            'cast_id': t.cast_id,
            'cast_name': t.cast.name_display if t.cast else None,
            'shop_name': t.cast.shop.name if t.cast and t.cast.shop else None,
            'area': t.area,
            'current_pv': t.current_pv,
            'previous_pv': t.previous_pv,
            'growth_rate': round(t.growth_rate, 2),
            'image_url': t.cast.image_url if t.cast else None,
        } for t in trending_casts]
    
    return jsonify(result)


# ============================================
# Banner API
# ============================================

@api_bp.route('/banners/<area>', methods=['GET'])
@limiter.limit("60 per minute")
def get_banners(area):
    """
    エリアのトップバナーを取得
    """
    if area not in Shop.AREAS:
        return jsonify({'error': 'Invalid area'}), 400
    
    banners = AdService.get_top_banner(area)
    
    result = [{
        'target_type': b['target_type'],
        'target_id': b['target'].id if b['target'] else None,
        'target_name': b['target'].name if b['target_type'] == 'shop' and b['target'] else (b['target'].name_display if b['target'] else None),
        'image_url': b['image_url'],
        'link_url': b['link_url'],
        'priority': b['priority'],
    } for b in banners]
    
    return jsonify({'banners': result})


# ============================================
# Badge API
# ============================================

@api_bp.route('/badges/<target_type>/<int:target_id>', methods=['GET'])
@limiter.limit("120 per minute")
def get_badges(target_type, target_id):
    """
    対象のバッジ情報を取得
    """
    if target_type not in ['shop', 'cast']:
        return jsonify({'error': 'Invalid target_type'}), 400
    
    if target_type == 'shop':
        badges = AdService.get_shop_badges(target_id)
    else:
        badges = AdService.get_cast_badges(target_id)
    
    best_badge = AdService.get_best_badge(target_type, target_id)
    
    return jsonify({
        'badges': badges,
        'best_badge': best_badge
    })


# ============================================
# Twilio 自動音声予約
# ============================================

@api_bp.route('/booking/call', methods=['POST'])
@limiter.limit("5 per hour")
def initiate_booking_call():
    """Twilio経由で自動音声予約コールを発信"""
    from flask import current_app
    import re

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'リクエストデータがありません'}), 400

    shop_id = data.get('shop_id')
    phone = data.get('phone', '').strip()

    if not shop_id or not phone:
        return jsonify({'success': False, 'error': '店舗IDと電話番号は必須です'}), 400

    if not re.match(r'^(\+81|0)\d{9,10}$', phone):
        return jsonify({'success': False, 'error': '有効な電話番号を入力してください（例: 090-1234-5678）'}), 400

    phone_clean = re.sub(r'[-\s]', '', phone)
    if phone_clean.startswith('0'):
        phone_e164 = '+81' + phone_clean[1:]
    else:
        phone_e164 = phone_clean

    account_sid = current_app.config.get('TWILIO_ACCOUNT_SID')
    if not account_sid:
        return jsonify({'success': False, 'error': '自動音声予約システムは現在準備中です'}), 503

    from ..services.twilio_service import initiate_call
    result = initiate_call(int(shop_id), phone_e164)

    if result['success']:
        return jsonify({
            'success': True,
            'message': 'お電話をおかけしています。しばらくお待ちください。',
            'call_sid': result.get('call_sid')
        })
    else:
        return jsonify({
            'success': False,
            'error': result.get('error', '発信に失敗しました')
        }), 500


@api_bp.route('/booking/call/status', methods=['GET'])
@limiter.limit("30 per minute")
def get_booking_call_status():
    """通話ステータスを取得"""
    call_sid = request.args.get('call_sid')
    if not call_sid:
        return jsonify({'error': 'call_sid is required'}), 400

    from ..services.twilio_service import get_call_status
    result = get_call_status(call_sid)
    return jsonify(result)
