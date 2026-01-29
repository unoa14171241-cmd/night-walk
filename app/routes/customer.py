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


# ==================== 口コミ評価 ====================

@customer_bp.route('/review/<int:shop_id>', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def submit_review(shop_id):
    """店舗への口コミ投稿"""
    from ..models.review import ShopReview
    from ..services.review_service import ReviewService
    
    shop = Shop.query.get_or_404(shop_id)
    
    if request.method == 'POST':
        rating = request.form.get('rating', type=int)
        phone_number = request.form.get('phone_number', '').strip()
        
        # バリデーション
        errors = []
        if not rating or not (1 <= rating <= 5):
            errors.append('評価を選択してください（1〜5）')
        if not phone_number:
            errors.append('電話番号を入力してください')
        elif not phone_number.replace('-', '').replace('+', '').isdigit():
            errors.append('有効な電話番号を入力してください')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('customer/review_form.html', 
                                   shop=shop, rating=rating, phone_number=phone_number)
        
        # 電話番号を正規化（ハイフン除去、国番号追加）
        normalized_phone = phone_number.replace('-', '').replace(' ', '')
        if normalized_phone.startswith('0'):
            normalized_phone = '+81' + normalized_phone[1:]
        elif not normalized_phone.startswith('+'):
            normalized_phone = '+81' + normalized_phone
        
        # 端末識別用フィンガープリント
        device_fingerprint = request.headers.get('User-Agent', '') + request.remote_addr
        import hashlib
        device_fingerprint = hashlib.sha256(device_fingerprint.encode()).hexdigest()[:32]
        
        # 口コミ投稿
        customer_id = current_user.id if current_user.is_authenticated and hasattr(current_user, 'is_customer') else None
        
        result = ReviewService.submit_review(
            shop_id=shop_id,
            rating=rating,
            phone_number=normalized_phone,
            customer_id=customer_id,
            device_fingerprint=device_fingerprint,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        if not result['success']:
            flash(result['error'], 'danger')
            return render_template('customer/review_form.html', 
                                   shop=shop, rating=rating, phone_number=phone_number)
        
        # SMS認証コードを送信
        verification = result['verification']
        ReviewService.send_sms_verification(normalized_phone, verification.verification_code)
        
        # 認証画面へリダイレクト
        session['pending_review_id'] = result['review'].id
        flash('認証コードを送信しました。SMSをご確認ください。', 'info')
        return redirect(url_for('customer.verify_review', shop_id=shop_id))
    
    return render_template('customer/review_form.html', shop=shop)


@customer_bp.route('/review/<int:shop_id>/verify', methods=['GET', 'POST'])
@limiter.limit("20 per hour")
def verify_review(shop_id):
    """口コミSMS認証"""
    from ..services.review_service import ReviewService
    
    shop = Shop.query.get_or_404(shop_id)
    review_id = session.get('pending_review_id')
    
    if not review_id:
        flash('認証が必要な口コミがありません。', 'warning')
        return redirect(url_for('customer.submit_review', shop_id=shop_id))
    
    if request.method == 'POST':
        verification_code = request.form.get('verification_code', '').strip()
        
        if not verification_code:
            flash('認証コードを入力してください。', 'danger')
            return render_template('customer/review_verify.html', shop=shop)
        
        # 認証実行
        customer_id = current_user.id if current_user.is_authenticated and hasattr(current_user, 'is_customer') else None
        
        result = ReviewService.verify_and_complete(
            review_id=review_id,
            verification_code=verification_code,
            customer_id=customer_id
        )
        
        if not result['success']:
            flash(result['error'], 'danger')
            return render_template('customer/review_verify.html', shop=shop)
        
        # 成功
        session.pop('pending_review_id', None)
        
        if result['points_rewarded'] > 0:
            flash(f'口コミを投稿しました！{result["points_rewarded"]}ポイントを獲得しました！', 'success')
        else:
            flash('口コミを投稿しました！', 'success')
        
        return redirect(url_for('public.shop_detail', shop_id=shop_id))
    
    return render_template('customer/review_verify.html', shop=shop)


@customer_bp.route('/review/<int:shop_id>/resend', methods=['POST'])
@limiter.limit("5 per hour")
def resend_review_code(shop_id):
    """認証コード再送信"""
    from ..services.review_service import ReviewService
    
    review_id = session.get('pending_review_id')
    
    if not review_id:
        flash('認証が必要な口コミがありません。', 'warning')
        return redirect(url_for('customer.submit_review', shop_id=shop_id))
    
    result = ReviewService.resend_verification_code(
        review_id=review_id,
        ip_address=request.remote_addr
    )
    
    if not result['success']:
        flash(result['error'], 'danger')
    else:
        # SMS送信
        ReviewService.send_sms_verification(
            result['verification'].phone_number,
            result['verification'].verification_code
        )
        flash('認証コードを再送信しました。', 'info')
    
    return redirect(url_for('customer.verify_review', shop_id=shop_id))


# ==================== 店舗ポイントカード ====================

@customer_bp.route('/point-cards')
@customer_login_required
def point_cards():
    """ポイントカード一覧"""
    from ..services.shop_point_service import ShopPointService
    
    cards = ShopPointService.get_customer_cards(current_user.id)
    rewards = ShopPointService.get_customer_rewards(current_user.id, valid_only=True)
    
    return render_template('customer/point_cards.html',
                           cards=cards,
                           rewards=rewards)


@customer_bp.route('/point-cards/<int:shop_id>')
@customer_login_required
def point_card_detail(shop_id):
    """店舗ポイントカード詳細"""
    from ..services.shop_point_service import ShopPointService
    from ..models.shop_point import ShopPointCard
    
    shop = Shop.query.get_or_404(shop_id)
    
    # ポイントカード設定
    card_config = ShopPointCard.query.filter_by(shop_id=shop_id).first()
    if not card_config or not card_config.is_active:
        flash('この店舗ではポイントカードが利用できません。', 'warning')
        return redirect(url_for('customer.point_cards'))
    
    # 顧客のポイント
    customer_point = ShopPointService.get_customer_card(current_user.id, shop_id)
    
    # 取引履歴
    transactions = ShopPointService.get_transaction_history(current_user.id, shop_id, limit=20)
    
    # 特典
    rewards = ShopPointService.get_customer_rewards(current_user.id, shop_id, valid_only=True)
    
    return render_template('customer/point_card_detail.html',
                           shop=shop,
                           card_config=card_config,
                           customer_point=customer_point,
                           transactions=transactions,
                           rewards=rewards)


@customer_bp.route('/point-cards/<int:shop_id>/exchange', methods=['POST'])
@customer_login_required
@limiter.limit("10 per hour")
def exchange_reward(shop_id):
    """特典を交換"""
    from ..services.shop_point_service import ShopPointService
    
    success, message, reward = ShopPointService.use_reward(current_user.id, shop_id)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    
    return redirect(url_for('customer.point_card_detail', shop_id=shop_id))
