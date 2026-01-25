"""
Night-Walk MVP - Vacancy Service
"""
from datetime import datetime
from ..extensions import db
from ..models.shop import Shop, VacancyStatus, VacancyHistory
from ..models.audit import AuditLog
from ..utils.logger import audit_log


def update_vacancy_status(shop_id, new_status, user_id=None, ip_address=None):
    """
    Update the vacancy status for a shop.
    
    Args:
        shop_id: Shop ID
        new_status: New status ('empty', 'busy', 'full', 'unknown')
        user_id: User ID who made the change
        ip_address: Client IP address
    
    Returns:
        VacancyStatus object or None on error
    """
    if new_status not in VacancyStatus.STATUSES:
        return None
    
    try:
        shop = Shop.query.get(shop_id)
        if not shop:
            return None
        
        # Get or create vacancy status
        vacancy = shop.vacancy_status
        if not vacancy:
            vacancy = VacancyStatus(shop_id=shop_id)
            db.session.add(vacancy)
        
        old_status = vacancy.status
        
        # Update status
        vacancy.status = new_status
        vacancy.updated_at = datetime.utcnow()
        vacancy.updated_by = user_id
        
        # Record history
        history = VacancyHistory(
            shop_id=shop_id,
            status=new_status,
            changed_by=user_id,
            ip_address=ip_address
        )
        db.session.add(history)
        
        db.session.commit()
        
        # Audit log
        audit_log(
            AuditLog.ACTION_VACANCY_UPDATE,
            'shop',
            shop_id,
            old_value={'status': old_status},
            new_value={'status': new_status}
        )
        
        return vacancy
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating vacancy status: {e}")
        return None


def get_vacancy_status(shop_id):
    """
    Get the current vacancy status for a shop.
    
    Args:
        shop_id: Shop ID
    
    Returns:
        dict with status info or None
    """
    vacancy = VacancyStatus.query.filter_by(shop_id=shop_id).first()
    
    if not vacancy:
        return {
            'status': 'unknown',
            'label': '−',
            'color': 'secondary',
            'updated_at': None,
        }
    
    return {
        'status': vacancy.status,
        'label': vacancy.label,
        'color': vacancy.color,
        'updated_at': vacancy.updated_at.isoformat() if vacancy.updated_at else None,
    }


def get_all_vacancy_statuses():
    """
    Get vacancy statuses for all active published shops.
    
    Returns:
        list of dicts with shop and vacancy info
    """
    shops = Shop.query.filter_by(is_published=True, is_active=True).all()
    
    result = []
    for shop in shops:
        vacancy = shop.vacancy_status
        result.append({
            'shop_id': shop.id,
            'shop_name': shop.name,
            'area': shop.area,
            'status': vacancy.status if vacancy else 'unknown',
            'label': vacancy.label if vacancy else '−',
            'color': vacancy.color if vacancy else 'secondary',
            'updated_at': vacancy.updated_at.isoformat() if vacancy and vacancy.updated_at else None,
        })
    
    return result
