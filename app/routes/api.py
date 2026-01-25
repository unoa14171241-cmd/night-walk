"""
Night-Walk MVP - Internal API Routes
"""
from datetime import datetime
from flask import Blueprint, jsonify, request, g
from flask_login import login_required, current_user
from ..extensions import db, limiter
from ..models.shop import Shop, VacancyStatus, VacancyHistory
from ..models.audit import AuditLog
from ..utils.decorators import shop_access_required
from ..utils.logger import audit_log
from ..utils.helpers import get_client_ip

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
            'business_hours': shop.business_hours,
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
