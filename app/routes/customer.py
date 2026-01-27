# app/routes/customer.py
"""一般ユーザー（カスタマー）用ルート"""

from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
import stripe
from ..extensions import db, limiter
from ..models import Customer, PointPackage, PointTransaction, Gift, Cast, GiftTransaction, Earning, Shop
from ..utils.logger import audit_log

customer_bp = Blueprint('customer', __name__)


def customer_login_required(f):
    """カスタマーログイン必須デコレータ"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('ログインが必要です。', 'warning')
            return redirect(url_for('customer.login', next=request.url))
        if not hasattr(current_user, 'is_customer') or not current_user.is_customer:
            flash('お客様専用ページです。', 'warning')
            return redirect(url_for('customer.login'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== 認証 ====================

@customer_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def register():
    """新規会員登録"""
    if current_user.is_authenticated and hasattr(current_user, 'is_customer'):
        return redirect(url_for('customer.mypage'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')
        nickname = request.form.get('nickname', '').strip()
        
        # バリデーション
        errors = []
        if not email:
            errors.append('メールアドレスを入力してください。')
        if not password:
            errors.append('パスワードを入力してください。')
        elif len(password) < 8:
            errors.append('パスワードは8文字以上で入力してください。')
        if password != password_confirm:
            errors.append('パスワードが一致しません。')
        if not nickname:
            errors.append('ニックネームを入力してください。')
        elif len(nickname) > 50:
            errors.append('ニックネームは50文字以内で入力してください。')
        
        # メール重複チェック
        if Customer.query.filter_by(email=email).first():
            errors.append('このメールアドレスは既に登録されています。')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('customer/register.html', 
                                   email=email, nickname=nickname)
        
        # ユーザー作成
        customer = Customer(
            email=email,
            nickname=nickname,
            point_balance=0
        )
        customer.set_password(password)
        
        db.session.add(customer)
        db.session.commit()
        
        audit_log('customer_register', f'新規会員登録: {email}')
        
        # 自動ログイン
        login_user(customer, remember=True)
        flash('会員登録が完了しました！', 'success')
        
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(url_for('customer.mypage'))
    
    return render_template('customer/register.html')


@customer_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    """ログイン"""
    if current_user.is_authenticated and hasattr(current_user, 'is_customer'):
        return redirect(url_for('customer.mypage'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        customer = Customer.query.filter_by(email=email).first()
        
        if customer and customer.check_password(password):
            if not customer.is_active:
                flash('このアカウントは無効になっています。', 'danger')
                return render_template('customer/login.html', email=email)
            
            login_user(customer, remember=bool(remember))
            customer.last_login_at = datetime.utcnow()
            db.session.commit()
            
            audit_log('customer_login', f'ログイン: {email}', customer_id=customer.id)
            
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('customer.mypage'))
        
        flash('メールアドレスまたはパスワードが正しくありません。', 'danger')
        return render_template('customer/login.html', email=email)
    
    return render_template('customer/login.html')


@customer_bp.route('/logout')
def logout():
    """ログアウト"""
    if current_user.is_authenticated and hasattr(current_user, 'is_customer'):
        audit_log('customer_logout', f'ログアウト: {current_user.email}', customer_id=current_user.id)
    logout_user()
    flash('ログアウトしました。', 'info')
    return redirect(url_for('public.index'))


# ==================== マイページ ====================

@customer_bp.route('/mypage')
@customer_login_required
def mypage():
    """マイページ"""
    # 最近の取引履歴
    recent_transactions = PointTransaction.query.filter_by(
        customer_id=current_user.id
    ).order_by(PointTransaction.created_at.desc()).limit(10).all()
    
    # 最近のギフト送信
    recent_gifts = GiftTransaction.query.filter_by(
        customer_id=current_user.id
    ).order_by(GiftTransaction.created_at.desc()).limit(5).all()
    
    return render_template('customer/mypage.html',
                           recent_transactions=recent_transactions,
                           recent_gifts=recent_gifts)


@customer_bp.route('/points/history')
@customer_login_required
def point_history():
    """ポイント履歴"""
    page = request.args.get('page', 1, type=int)
    transactions = PointTransaction.query.filter_by(
        customer_id=current_user.id
    ).order_by(PointTransaction.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    return render_template('customer/point_history.html', transactions=transactions)


# ==================== ポイント購入 ====================

@customer_bp.route('/points/buy')
@customer_login_required
def buy_points():
    """ポイント購入ページ"""
    packages = PointPackage.get_active_packages()
    return render_template('customer/buy_points.html', packages=packages)


@customer_bp.route('/points/buy/<int:package_id>', methods=['POST'])
@customer_login_required
@limiter.limit("5 per minute")
def purchase_package(package_id):
    """ポイントパッケージ購入処理（Stripe Checkout）"""
    package = PointPackage.query.get_or_404(package_id)
    
    if not package.is_active:
        flash('このパッケージは現在購入できません。', 'warning')
        return redirect(url_for('customer.buy_points'))
    
    api_key = current_app.config.get('STRIPE_SECRET_KEY')
    
    if not api_key:
        flash('決済システムが設定されていません。', 'danger')
        return redirect(url_for('customer.buy_points'))
    
    try:
        # Stripe APIキー設定
        stripe.api_key = api_key
        
        # Stripe Checkout Session作成
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'jpy',
                    'product_data': {
                        'name': f'Night-Walk ポイント - {package.name}',
                        'description': f'{package.total_points:,}pt（ボーナス{package.bonus_points:,}pt含む）',
                    },
                    'unit_amount': package.price,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=url_for('customer.purchase_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('customer.buy_points', _external=True),
            metadata={
                'customer_id': str(current_user.id),
                'package_id': str(package.id),
                'type': 'point_purchase'
            }
        )
        
        return redirect(checkout_session.url)
        
    except Exception as e:
        current_app.logger.error(f'Stripe checkout error: {e}')
        flash('決済処理でエラーが発生しました。', 'danger')
        return redirect(url_for('customer.buy_points'))


@customer_bp.route('/points/success')
@customer_login_required
def purchase_success():
    """購入成功ページ"""
    session_id = request.args.get('session_id')
    if not session_id:
        return redirect(url_for('customer.mypage'))
    
    api_key = current_app.config.get('STRIPE_SECRET_KEY')
    
    try:
        # Stripe APIキー設定
        stripe.api_key = api_key
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        
        if checkout_session.payment_status == 'paid':
            # メタデータからパッケージ情報を取得
            package_id = int(checkout_session.metadata.get('package_id', 0))
            customer_id = int(checkout_session.metadata.get('customer_id', 0))
            
            # 既に処理済みかチェック
            existing = PointTransaction.query.filter_by(
                stripe_payment_intent_id=checkout_session.payment_intent
            ).first()
            
            if not existing and customer_id == current_user.id:
                package = PointPackage.query.get(package_id)
                if package:
                    # ポイント付与
                    current_user.add_points(package.total_points)
                    
                    # 取引履歴作成
                    transaction = PointTransaction(
                        customer_id=current_user.id,
                        transaction_type=PointTransaction.TYPE_PURCHASE,
                        amount=package.total_points,
                        balance_after=current_user.point_balance,
                        package_id=package.id,
                        payment_amount=package.price,
                        stripe_payment_intent_id=checkout_session.payment_intent,
                        description=f'{package.name} 購入'
                    )
                    db.session.add(transaction)
                    db.session.commit()
                    
                    audit_log('point_purchase', 
                              f'ポイント購入: {package.name} ({package.total_points}pt)', 
                              customer_id=current_user.id)
                    
                    flash(f'{package.total_points:,}ポイントを購入しました！', 'success')
            else:
                flash('ポイントが付与されました。', 'success')
        
    except Exception as e:
        current_app.logger.error(f'Purchase success error: {e}')
    
    return redirect(url_for('customer.mypage'))


# ==================== ギフト送信 ====================

@customer_bp.route('/cast/<int:cast_id>')
def cast_detail(cast_id):
    """キャスト詳細・ギフト送信ページ"""
    cast = Cast.query.get_or_404(cast_id)
    
    if not cast.is_active:
        flash('このキャストは現在非公開です。', 'warning')
        return redirect(url_for('public.shop_detail', shop_id=cast.shop_id))
    
    gifts = Gift.get_active_gifts()
    
    return render_template('customer/cast_detail.html', cast=cast, gifts=gifts)


@customer_bp.route('/cast/<int:cast_id>/gift', methods=['POST'])
@customer_login_required
@limiter.limit("30 per minute")
def send_gift(cast_id):
    """ギフト送信"""
    cast = Cast.query.get_or_404(cast_id)
    
    if not cast.is_active or not cast.is_accepting_gifts:
        flash('このキャストは現在ギフトを受け付けていません。', 'warning')
        return redirect(url_for('customer.cast_detail', cast_id=cast_id))
    
    gift_id = request.form.get('gift_id', type=int)
    message = request.form.get('message', '').strip()[:200]  # 200文字制限
    
    gift = Gift.query.get_or_404(gift_id)
    
    if not gift.is_active:
        flash('このギフトは選択できません。', 'warning')
        return redirect(url_for('customer.cast_detail', cast_id=cast_id))
    
    # ポイント残高チェック
    if not current_user.can_use_points(gift.points):
        flash('ポイントが不足しています。', 'warning')
        return redirect(url_for('customer.buy_points'))
    
    # ポイント消費
    current_user.use_points(gift.points)
    
    # ギフト取引作成
    gift_tx = GiftTransaction(
        customer_id=current_user.id,
        cast_id=cast.id,
        gift_id=gift.id,
        shop_id=cast.shop_id,
        points_used=gift.points,
        message=message,
        cast_amount=gift.cast_amount,
        shop_amount=gift.shop_amount,
        platform_amount=gift.platform_amount,
        status=GiftTransaction.STATUS_COMPLETED
    )
    db.session.add(gift_tx)
    db.session.flush()  # IDを取得
    
    # ポイント取引履歴
    point_tx = PointTransaction(
        customer_id=current_user.id,
        transaction_type=PointTransaction.TYPE_GIFT,
        amount=-gift.points,
        balance_after=current_user.point_balance,
        gift_transaction_id=gift_tx.id,
        description=f'{cast.name_display}さんに{gift.name}を送信'
    )
    db.session.add(point_tx)
    
    # キャスト集計更新
    cast.add_gift(gift.points, gift.cast_amount)
    
    # 収益レコード作成
    earnings = Earning.create_from_gift(gift_tx)
    for earning in earnings:
        db.session.add(earning)
    
    db.session.commit()
    
    audit_log('gift_send', 
              f'ギフト送信: {cast.name_display}に{gift.name}({gift.points}pt)', 
              customer_id=current_user.id)
    
    flash(f'{cast.name_display}さんに{gift.name}を送りました！', 'success')
    return redirect(url_for('customer.cast_detail', cast_id=cast_id))


# ==================== ギフト履歴 ====================

@customer_bp.route('/gifts/history')
@customer_login_required
def gift_history():
    """ギフト送信履歴"""
    page = request.args.get('page', 1, type=int)
    gifts = GiftTransaction.query.filter_by(
        customer_id=current_user.id
    ).order_by(GiftTransaction.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    return render_template('customer/gift_history.html', gifts=gifts)
