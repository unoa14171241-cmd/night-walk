"""
Night-Walk MVP - Public Routes (公開ページ)
"""
from flask import Blueprint, render_template, request, current_app, session, make_response, flash, redirect, url_for
from flask_login import current_user
from ..models.shop import Shop, VacancyStatus
from ..models.content import Announcement, Advertisement
from ..models.gift import Cast
from ..services.ad_service import AdService
from ..services.trending_service import TrendingService

public_bp = Blueprint('public', __name__)


@public_bp.after_request
def add_cache_control(response):
    """
    店舗情報の即時反映のためキャッシュ制御を追加。
    動的コンテンツはキャッシュしない設定。
    """
    # HTMLページはキャッシュしない（即時反映のため）
    if response.content_type and 'text/html' in response.content_type:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


@public_bp.route('/')
def index():
    """Home page - search page with announcements and ads."""
    # Get active announcements
    announcements = Announcement.get_active(limit=5)
    
    # Get banner ads (既存の広告 + entitlementベースのバナー)
    top_ads = Advertisement.get_active(position='top', limit=3)
    
    # エリア別トップバナー（entitlementベース）
    area_banners = {}
    for area in Shop.AREAS:
        area_banners[area] = AdService.get_top_banner(area)[:3]
    
    # Get featured shops (広告優先ロジック適用)
    featured_shops_raw = AdService.get_search_results(featured_only=True)[:6]
    featured_shops = AdService.enrich_shop_list(featured_shops_raw)
    
    # Get recent shops
    recent_shops_raw = Shop.query.filter_by(
        is_published=True, 
        is_active=True
    ).order_by(Shop.created_at.desc()).limit(6).all()
    recent_shops = AdService.enrich_shop_list(recent_shops_raw)
    
    # 急上昇（店舗・キャスト）
    trending_shops = TrendingService.get_trending_shops(limit=5)
    trending_casts = TrendingService.get_trending_casts(limit=5)
    
    return render_template('public/index.html',
                          announcements=announcements,
                          top_ads=top_ads,
                          area_banners=area_banners,
                          featured_shops=featured_shops,
                          recent_shops=recent_shops,
                          trending_shops=trending_shops,
                          trending_casts=trending_casts,
                          areas=Shop.AREAS,
                          scenes=Shop.SCENES,
                          scene_groups=Shop.SCENE_GROUPS,
                          categories=Shop.CATEGORIES,
                          category_labels=Shop.CATEGORY_LABELS,
                          price_ranges=Shop.PRICE_RANGES,
                          vacancy_labels=VacancyStatus.STATUS_LABELS,
                          vacancy_colors=VacancyStatus.STATUS_COLORS)


@public_bp.route('/search')
def search():
    """Search results page."""
    # Get search parameters
    keyword = request.args.get('q', '').strip()
    area = request.args.get('area', '')
    scene = request.args.get('scene', '')
    category = request.args.get('category', '')
    price_range_key = request.args.get('price', '')
    vacancy = request.args.get('vacancy', '')
    has_job = request.args.get('has_job', '') == '1'
    
    # シーンが選択されている場合、そのシーンのカテゴリリストを取得
    scene_categories = []
    if scene and scene in Shop.SCENES:
        scene_categories = Shop.get_categories_by_scene(scene)
    
    # Perform search with ad priority (広告優先ロジック適用)
    shops = AdService.get_search_results(
        keyword=keyword if keyword else None,
        area=area if area else None,
        scene=scene if scene else None,
        category=category if category else None,
        price_range_key=price_range_key if price_range_key else None,
        vacancy_status=vacancy if vacancy else None,
        has_job=has_job if has_job else None
    )
    
    # 店舗にバッジ情報を付加
    shops_with_badges = AdService.enrich_shop_list(shops)
    
    # Get ads for sidebar
    sidebar_ads = Advertisement.get_active(position='sidebar', limit=2)
    
    # 一覧内広告を取得
    inline_ads = AdService.get_inline_ads(area=area if area else None, limit=3)
    
    return render_template('public/search.html',
                          shops=shops,
                          shops_with_badges=shops_with_badges,
                          inline_ads=inline_ads,
                          keyword=keyword,
                          selected_area=area,
                          selected_scene=scene,
                          selected_category=category,
                          selected_price=price_range_key,
                          selected_vacancy=vacancy,
                          has_job=has_job,
                          areas=Shop.AREAS,
                          scenes=Shop.SCENES,
                          scene_groups=Shop.SCENE_GROUPS,
                          scene_categories=scene_categories,
                          categories=Shop.CATEGORIES,
                          category_labels=Shop.CATEGORY_LABELS,
                          price_ranges=Shop.PRICE_RANGES,
                          sidebar_ads=sidebar_ads,
                          vacancy_labels=VacancyStatus.STATUS_LABELS,
                          vacancy_colors=VacancyStatus.STATUS_COLORS,
                          vacancy_statuses=VacancyStatus.STATUSES[:3])  # empty, busy, full


@public_bp.route('/shops')
def shops():
    """Shop list with area filter (legacy route)."""
    area = request.args.get('area', '')
    
    query = Shop.query.filter_by(is_published=True, is_active=True)
    
    if area and area in Shop.AREAS:
        query = query.filter_by(area=area)
    
    shops = query.order_by(Shop.is_featured.desc(), Shop.name).all()
    
    return render_template('public/shop_list.html',
                          shops=shops,
                          areas=Shop.AREAS,
                          selected_area=area,
                          vacancy_labels=VacancyStatus.STATUS_LABELS,
                          vacancy_colors=VacancyStatus.STATUS_COLORS)


@public_bp.route('/shops/<int:shop_id>')
def shop_detail(shop_id):
    """Shop detail page."""
    import uuid
    from ..extensions import db
    from ..models.cast_shift import CastShift
    
    shop = Shop.query.filter_by(
        id=shop_id,
        is_published=True,
        is_active=True
    ).first_or_404()
    
    # PVを記録
    customer_id = None
    session_id = None
    
    if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
        if hasattr(current_user, 'is_customer') and current_user.is_customer:
            customer_id = current_user.id
    
    if not customer_id:
        if 'visitor_id' not in session:
            session['visitor_id'] = str(uuid.uuid4())
        session_id = session['visitor_id']
    
    recorded = TrendingService.record_shop_view(
        shop_id=shop_id,
        customer_id=customer_id,
        session_id=session_id,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string if request.user_agent else None,
        referrer=request.referrer,
        page_type='detail'
    )
    
    if recorded:
        db.session.commit()
    
    # Get active job if any
    job = shop.active_job
    
    # 求人表示可能か確認
    can_show_job = AdService.can_show_job(shop_id)
    
    # Get shop images
    images = shop.all_images
    
    # Get active casts
    casts = Cast.get_active_by_shop(shop_id)
    
    # キャスト出勤表示可能か確認
    can_show_shifts = AdService.can_show_cast_shift(shop_id)
    working_casts = []
    today_scheduled_shifts = []
    today_working_cast_ids = set()
    today_scheduled_cast_ids = set()
    if can_show_shifts:
        today_shifts = CastShift.get_today_shifts(shop_id)
        working_casts = CastShift.get_working_now(shop_id)
        today_working_cast_ids = {s.cast_id for s in working_casts}
        today_scheduled_shifts = [s for s in today_shifts if s.cast_id not in today_working_cast_ids]
        today_scheduled_cast_ids = {s.cast_id for s in today_scheduled_shifts}
    
    # バッジ情報を取得
    shop_badges = AdService.get_shop_badges(shop_id)
    best_badge = AdService.get_best_badge('shop', shop_id)
    
    # 有料プランフォールバック（エンタイトルメント未同期でもバッジ表示）
    if not shop_badges.get('premium_badge'):
        paid_plan_shops = AdService.get_paid_plan_shop_ids()
        if shop_id in paid_plan_shops:
            shop_badges['premium_badge'] = True
            if not best_badge:
                best_badge = {'type': 'premium', 'rank': None, 'label': '優良店', 'color': 'premium'}
    
    # 口コミ評価データを取得
    from ..services.review_service import ReviewService
    review_data = ReviewService.get_shop_rating_summary(shop_id)
    recent_reviews = ReviewService.get_recent_reviews(shop_id, limit=5)
    
    return render_template('public/shop_detail.html',
                          shop=shop,
                          job=job if can_show_job else None,
                          can_show_job=can_show_job,
                          images=images,
                          casts=casts,
                          working_casts=working_casts,
                          today_scheduled_shifts=today_scheduled_shifts,
                          today_working_cast_ids=today_working_cast_ids,
                          today_scheduled_cast_ids=today_scheduled_cast_ids,
                          can_show_shifts=can_show_shifts,
                          shop_badges=shop_badges,
                          best_badge=best_badge,
                          review_data=review_data,
                          recent_reviews=recent_reviews,
                          vacancy_labels=VacancyStatus.STATUS_LABELS,
                          vacancy_colors=VacancyStatus.STATUS_COLORS)


@public_bp.route('/casts/<int:cast_id>')
def cast_detail(cast_id):
    """キャスト詳細ページ（PVカウント発火）"""
    import uuid
    from ..extensions import db
    from ..services.ranking_service import RankingService
    
    cast = Cast.query.filter_by(id=cast_id, is_active=True).first_or_404()
    
    # 店舗が公開されているか確認
    if not cast.shop or not cast.shop.is_published or not cast.shop.is_active:
        from flask import abort
        abort(404)
    
    # PVを記録
    customer_id = None
    session_id = None
    
    if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
        if hasattr(current_user, 'is_customer') and current_user.is_customer:
            customer_id = current_user.id
    
    if not customer_id:
        # セッションIDを使用（非ログインユーザー）
        if 'visitor_id' not in session:
            session['visitor_id'] = str(uuid.uuid4())
        session_id = session['visitor_id']
    
    # PV記録
    recorded = RankingService.record_page_view(
        cast_id=cast_id,
        customer_id=customer_id,
        session_id=session_id,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string if request.user_agent else None
    )
    
    if recorded:
        db.session.commit()
    
    # ギフト一覧
    from ..models.gift import Gift
    from ..models.cast_tag import CastTag
    from ..models.cast_image import CastImage
    from ..models.cast_birthday import CastBirthday
    from ..models.cast_shift import CastShift
    gifts = Gift.get_active_gifts()
    
    # バッジ情報を取得
    cast_badges = AdService.get_cast_badges(cast_id)
    best_badge = AdService.get_best_badge('cast', cast_id)
    
    # タグ・画像・誕生日・シフト
    cast_tags = CastTag.get_tags_by_cast(cast_id)
    gallery = CastImage.get_gallery(cast_id)
    birthdays = CastBirthday.get_birthdays(cast_id)
    
    # 今週のシフト
    from datetime import date, timedelta
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # 月曜
    week_end = week_start + timedelta(days=6)  # 日曜
    shifts = CastShift.query.filter(
        CastShift.cast_id == cast_id,
        CastShift.shift_date >= week_start,
        CastShift.shift_date <= week_end
    ).order_by(CastShift.shift_date).all()
    
    return render_template('public/cast_detail.html',
                          cast=cast,
                          shop=cast.shop,
                          gifts=gifts,
                          cast_badges=cast_badges,
                          best_badge=best_badge,
                          vacancy_labels=VacancyStatus.STATUS_LABELS,
                          vacancy_colors=VacancyStatus.STATUS_COLORS,
                          cast_tags=cast_tags,
                          gallery=gallery,
                          birthdays=birthdays,
                          shifts=shifts,
                          tag_category_labels=CastTag.CATEGORY_LABELS,
                          tag_category_icons=CastTag.CATEGORY_ICONS)


@public_bp.route('/shops/<int:shop_id>/booking')
def booking(shop_id):
    """Booking page - phone reservation."""
    shop = Shop.query.filter_by(
        id=shop_id,
        is_published=True,
        is_active=True
    ).first_or_404()
    
    # Check if Twilio is configured
    twilio_configured = bool(current_app.config.get('TWILIO_ACCOUNT_SID'))
    
    return render_template('public/booking.html',
                          shop=shop,
                          twilio_configured=twilio_configured)


@public_bp.route('/ads/<int:ad_id>/click')
def ad_click(ad_id):
    """Track ad click and redirect."""
    from ..extensions import db
    
    ad = Advertisement.query.get_or_404(ad_id)
    ad.record_click()
    db.session.commit()
    
    if ad.link_url:
        from flask import redirect
        return redirect(ad.link_url)
    
    return redirect('/')


# ============================================
# Ranking Pages (ランキング)
# ============================================

@public_bp.route('/ranking')
def ranking_index():
    """ランキングトップ - エリア選択"""
    from ..models.ranking import AREA_DEFINITIONS
    from ..services.ranking_service import RankingService
    
    # 有効なエリア一覧
    areas = RankingService.get_active_areas()
    
    # 各エリアのTOP1を取得
    top1_list = RankingService.get_top1_casts()
    
    return render_template('public/ranking_index.html',
                          areas=areas,
                          area_definitions=AREA_DEFINITIONS,
                          top1_list=top1_list)


@public_bp.route('/ranking/<area>')
def ranking_area(area):
    """エリア別ランキング"""
    from datetime import date
    from ..models.ranking import CastMonthlyRanking, AREA_DEFINITIONS, RankingConfig
    from ..services.ranking_service import RankingService
    
    # エリア検証
    active_areas = RankingService.get_active_areas()
    if area not in active_areas:
        from flask import abort
        abort(404)
    
    # 年月パラメータ（デフォルトは前月の確定ランキング）
    today = date.today()
    if today.month == 1:
        default_year, default_month = today.year - 1, 12
    else:
        default_year, default_month = today.year, today.month - 1
    
    year = request.args.get('year', default_year, type=int)
    month = request.args.get('month', default_month, type=int)
    
    # ランキング取得
    top_count = RankingConfig.get('ranking_top_count', 100)
    rankings = CastMonthlyRanking.get_ranking(area, year, month, limit=top_count)
    
    # TOP1を特別に取得
    top1 = rankings[0] if rankings else None
    
    # エリア情報
    area_info = AREA_DEFINITIONS.get(area, {})
    
    return render_template('public/ranking_area.html',
                          area=area,
                          area_info=area_info,
                          rankings=rankings,
                          top1=top1,
                          year=year,
                          month=month)


@public_bp.route('/trending')
def trending():
    """急上昇ページ"""
    area = request.args.get('area', '')
    target_type = request.args.get('type', 'shop')  # 'shop' or 'cast'
    
    if area and area not in Shop.AREAS:
        area = None
    
    if target_type == 'cast':
        trending_list = TrendingService.get_trending_casts(area=area, limit=50)
    else:
        trending_list = TrendingService.get_trending_shops(area=area, limit=50)
    
    return render_template('public/trending.html',
                          trending_list=trending_list,
                          target_type=target_type,
                          selected_area=area,
                          areas=Shop.AREAS)


@public_bp.route('/ranking/<area>/top1')
def ranking_top1(area):
    """エリアTOP1特集ページ（アプリの顔）"""
    from datetime import date
    from ..models.ranking import CastMonthlyRanking, CastBadgeHistory, AREA_DEFINITIONS
    from ..services.ranking_service import RankingService
    
    # エリア検証
    active_areas = RankingService.get_active_areas()
    if area not in active_areas:
        from flask import abort
        abort(404)
    
    # 年月パラメータ
    today = date.today()
    if today.month == 1:
        default_year, default_month = today.year - 1, 12
    else:
        default_year, default_month = today.year, today.month - 1
    
    year = request.args.get('year', default_year, type=int)
    month = request.args.get('month', default_month, type=int)
    
    # TOP1を取得
    top1 = CastMonthlyRanking.get_top1(area, year, month)
    
    if not top1:
        from flask import abort
        abort(404)
    
    # バッジ情報
    badge = CastBadgeHistory.query.filter_by(
        cast_id=top1.cast_id,
        area=area,
        year=year,
        month=month,
        badge_type='area_top1'
    ).first()
    
    # エリア情報
    area_info = AREA_DEFINITIONS.get(area, {})
    
    return render_template('public/ranking_top1.html',
                          area=area,
                          area_info=area_info,
                          top1=top1,
                          badge=badge,
                          year=year,
                          month=month)


@public_bp.route('/apply', methods=['GET', 'POST'])
def shop_apply():
    """店舗掲載申し込みページ"""
    from flask import flash, redirect, url_for
    from ..models.shop import Shop
    from ..models.user import User
    from ..extensions import db
    import secrets
    import string
    
    if request.method == 'POST':
        # フォームデータ取得
        shop_name = request.form.get('shop_name', '').strip()
        area = request.form.get('area', '')
        category = request.form.get('category', '')
        contact_name = request.form.get('contact_name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        message = request.form.get('message', '').strip()
        
        # 振込口座情報
        bank_name = request.form.get('bank_name', '').strip()
        bank_branch = request.form.get('bank_branch', '').strip()
        account_type = request.form.get('account_type', '').strip()
        account_number = request.form.get('account_number', '').strip()
        account_holder = request.form.get('account_holder', '').strip()
        
        # 紹介コード（任意）
        referral_code = request.form.get('referral_code', '').strip().upper()
        
        # バリデーション
        errors = []
        if not shop_name:
            errors.append('店舗名は必須です。')
        if not area or area not in Shop.AREAS:
            errors.append('エリアを選択してください。')
        if not category or category not in Shop.CATEGORIES:
            errors.append('業態を選択してください。')
        if not contact_name:
            errors.append('担当者名は必須です。')
        if not email:
            errors.append('メールアドレスは必須です。')
        elif '@' not in email:
            errors.append('有効なメールアドレスを入力してください。')
        if not phone:
            errors.append('電話番号は必須です。')
        
        # 口座情報バリデーション
        if not bank_name:
            errors.append('金融機関名は必須です。')
        if not bank_branch:
            errors.append('支店名は必須です。')
        if not account_type or account_type not in ['普通', '当座']:
            errors.append('口座種別を選択してください。')
        if not account_number:
            errors.append('口座番号は必須です。')
        elif not account_number.isdigit() or len(account_number) < 7 or len(account_number) > 8:
            errors.append('口座番号は7〜8桁の数字で入力してください。')
        if not account_holder:
            errors.append('口座名義は必須です。')
        
        # 紹介コードバリデーション（入力された場合のみ）
        referral_obj = None
        if referral_code:
            from ..models.referral import ShopReferral
            referral_obj = ShopReferral.get_by_code(referral_code)
            if not referral_obj:
                errors.append('紹介コードが見つかりません。')
            elif not referral_obj.is_valid:
                errors.append('この紹介コードは無効または期限切れです。')
        
        # 重複チェック
        existing_shop = Shop.query.filter_by(name=shop_name, area=area).first()
        if existing_shop:
            errors.append('同名の店舗が既に登録されています。')
        
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            errors.append('このメールアドレスは既に使用されています。')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('public/shop_apply.html',
                                   areas=Shop.AREAS,
                                   categories=Shop.CATEGORIES,
                                   category_labels=Shop.CATEGORY_LABELS,
                                   form_data={
                                       'shop_name': shop_name,
                                       'area': area,
                                       'category': category,
                                       'contact_name': contact_name,
                                       'email': email,
                                       'phone': phone,
                                       'message': message,
                                       'bank_name': bank_name,
                                       'bank_branch': bank_branch,
                                       'account_type': account_type,
                                       'account_number': account_number,
                                       'account_holder': account_holder,
                                       'referral_code': referral_code
                                   })
        
        try:
            # 店舗を審査待ち状態で作成
            shop = Shop(
                name=shop_name,
                area=area,
                category=category,
                phone=phone,
                review_status=Shop.STATUS_PENDING,
                review_notes=f'担当者: {contact_name}\nメール: {email}\n備考: {message}' if message else f'担当者: {contact_name}\nメール: {email}',
                is_active=False,
                is_published=False,
                # 振込口座情報
                bank_name=bank_name,
                bank_branch=bank_branch,
                account_type=account_type,
                account_number=account_number,
                account_holder=account_holder
            )
            db.session.add(shop)
            db.session.flush()  # shop.idを取得
            
            # 仮パスワード生成
            temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
            
            # ユーザー作成（店舗オーナー）
            user = User(
                email=email,
                name=contact_name,
                role='shop_owner'
            )
            user.set_password(temp_password)
            db.session.add(user)
            db.session.flush()
            
            # ShopMemberとして紐付け
            from ..models.user import ShopMember
            shop_member = ShopMember(
                user_id=user.id,
                shop_id=shop.id,
                role='owner'
            )
            db.session.add(shop_member)
            
            # 紹介コードの紐付け
            if referral_code and referral_obj and referral_obj.is_valid:
                from ..models.referral import ShopReferral
                referral_obj.referred_shop_id = shop.id
                referral_obj.status = ShopReferral.STATUS_USED
                referral_obj.used_at = datetime.utcnow()
            
            # 申込情報を保存（審査完了時のメール送信用）
            referral_note = f'\n紹介コード: {referral_code}' if referral_code else ''
            shop.review_notes = f'担当者: {contact_name}\nメール: {email}\n仮パスワード: {temp_password}\n備考: {message}{referral_note}' if message else f'担当者: {contact_name}\nメール: {email}\n仮パスワード: {temp_password}{referral_note}'
            
            db.session.commit()
            
            flash('お申し込みありがとうございます！審査完了後、ご登録のメールアドレスにログイン情報をお送りします。', 'success')
            return redirect(url_for('public.shop_apply_complete'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Shop application error: {e}", exc_info=True)
            flash(f'申し込み処理中にエラーが発生しました: {str(e)}', 'danger')
            return render_template('public/shop_apply.html',
                                   areas=Shop.AREAS,
                                   categories=Shop.CATEGORIES,
                                   category_labels=Shop.CATEGORY_LABELS,
                                   form_data={
                                       'shop_name': shop_name,
                                       'area': area,
                                       'category': category,
                                       'contact_name': contact_name,
                                       'email': email,
                                       'phone': phone,
                                       'message': message,
                                       'bank_name': bank_name,
                                       'bank_branch': bank_branch,
                                       'account_type': account_type,
                                       'account_number': account_number,
                                       'account_holder': account_holder,
                                       'referral_code': referral_code
                                   })
    
    return render_template('public/shop_apply.html',
                           areas=Shop.AREAS,
                           categories=Shop.CATEGORIES,
                           category_labels=Shop.CATEGORY_LABELS,
                           form_data=None)


@public_bp.route('/apply/complete')
def shop_apply_complete():
    """店舗申込完了ページ"""
    return render_template('public/shop_apply_complete.html')


# ==================== FAQ ====================

@public_bp.route('/faq')
def faq():
    """FAQページ"""
    faq_items = [
        {
            'q': 'Night-Walkとは何ですか？',
            'a': 'Night-Walkは岡山・倉敷エリアに特化したナイトレジャー情報ポータルサイトです。キャバクラ、ガールズバー、スナック、ラウンジなどの店舗情報、空席状況のリアルタイム確認、キャストランキング、口コミ情報などを提供しています。'
        },
        {
            'q': '掲載は無料ですか？',
            'a': '基本的な店舗掲載は無料でご利用いただけます。より多くの集客機能（スタンプカード、優先表示、求人掲載など）をご利用いただける有料プランもご用意しています。'
        },
        {
            'q': '岡山以外のエリアにも対応していますか？',
            'a': '現在は岡山市・倉敷市エリアを中心にサービスを展開しています。今後、中国・四国地方を中心にエリア拡大を予定しています。'
        },
        {
            'q': '送客管理とは何ですか？',
            'a': '送客管理は、Night-Walk経由で店舗に来店されたお客様を自動的に記録・管理する機能です。どの経路からの集客が多いかをデータで確認でき、効果的なマーケティング戦略の立案に役立ちます。'
        },
        {
            'q': 'スタンプカード機能とは？',
            'a': '来店ごとにスタンプが貯まるデジタルスタンプカード機能です。ブロンズ・シルバー・ゴールド・プラチナのランク制度があり、ランクアップで特典が受けられます。有料プランをご契約の店舗様でご利用いただけます。'
        },
        {
            'q': '口コミはどのように投稿しますか？',
            'a': '各店舗の詳細ページから口コミを投稿できます。SMS認証を行った上で、星評価とコメントを入力して投稿します。投稿された口コミは店舗の評価に反映されます。'
        },
        {
            'q': 'キャストランキングの仕組みは？',
            'a': 'キャストランキングはページビュー数とギフトポイントを合算して毎月集計されます。エリア別にTOP10を発表し、上位キャストにはバッジが付与されます。'
        },
        {
            'q': '店舗掲載の申し込み方法は？',
            'a': 'トップページまたはフッターの「店舗掲載申し込み」リンクからお申し込みいただけます。必要情報を入力して送信後、審査を経て掲載が開始されます。'
        },
    ]

    return render_template('public/faq.html', faq_items=faq_items)


# ==================== Blog ====================

@public_bp.route('/blog')
def blog_index():
    """ブログ一覧"""
    from ..models.blog import BlogPost
    posts = BlogPost.get_published()
    return render_template('public/blog_index.html', posts=posts)


@public_bp.route('/blog/<slug>')
def blog_detail(slug):
    """ブログ記事詳細"""
    from ..models.blog import BlogPost
    post = BlogPost.get_by_slug(slug)
    if not post:
        from flask import abort
        abort(404)
    return render_template('public/blog_detail.html', post=post)


# ==================== Slug Routes ====================

@public_bp.route('/shops/s/<slug>')
def shop_detail_slug(slug):
    """スラッグベースの店舗詳細（SEO用）"""
    shop = Shop.query.filter_by(slug=slug, is_published=True, is_active=True).first()
    if not shop:
        from flask import abort
        abort(404)
    return redirect(url_for('public.shop_detail', shop_id=shop.id), code=301)


@public_bp.route('/casts/c/<slug>')
def cast_detail_slug(slug):
    """スラッグベースのキャスト詳細（SEO用）"""
    cast = Cast.query.filter_by(slug=slug, is_active=True).first()
    if not cast:
        from flask import abort
        abort(404)
    return redirect(url_for('public.cast_detail', cast_id=cast.id), code=301)


# ==================== SEO ====================

@public_bp.route('/sitemap.xml')
def sitemap():
    """動的sitemap.xml生成"""
    from flask import Response, url_for
    from datetime import datetime
    import os
    
    base_url = os.environ.get('BASE_URL', request.url_root.rstrip('/'))
    
    # XML開始
    xml_content = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_content.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    # 静的ページ
    static_pages = [
        ('public.index', 'daily', '1.0'),
        ('public.search', 'daily', '0.9'),
        ('public.ranking_index', 'daily', '0.8'),
        ('public.trending', 'daily', '0.7'),
        ('public.faq', 'monthly', '0.6'),
        ('public.blog_index', 'weekly', '0.7'),
        ('public.shop_apply', 'monthly', '0.5'),
    ]
    
    for endpoint, changefreq, priority in static_pages:
        try:
            url = url_for(endpoint, _external=True)
            xml_content.append(f'''  <url>
    <loc>{url}</loc>
    <changefreq>{changefreq}</changefreq>
    <priority>{priority}</priority>
  </url>''')
        except Exception:
            pass
    
    # エリア別ランキングページ
    for area in Shop.AREAS:
        try:
            url = url_for('public.ranking_area', area=area, _external=True)
            xml_content.append(f'''  <url>
    <loc>{url}</loc>
    <changefreq>daily</changefreq>
    <priority>0.7</priority>
  </url>''')
        except Exception:
            pass
    
    # 公開中の店舗ページ
    published_shops = Shop.query.filter_by(
        is_active=True, 
        is_published=True,
        is_demo=False
    ).all()
    
    for shop in published_shops:
        try:
            url = url_for('public.shop_detail', shop_id=shop.id, _external=True)
            lastmod_tag = ''
            if shop.updated_at:
                lastmod_tag = f'\n    <lastmod>{shop.updated_at.strftime("%Y-%m-%d")}</lastmod>'
            xml_content.append(f'''  <url>
    <loc>{url}</loc>{lastmod_tag}
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>''')
        except Exception:
            pass
    
    # 公開中のキャストページ
    from ..models.gift import Cast
    published_casts = Cast.query.filter_by(is_active=True, is_visible=True).all()
    
    for cast in published_casts:
        if cast.shop and cast.shop.is_demo:
            continue
        try:
            url = url_for('public.cast_detail', cast_id=cast.id, _external=True)
            lastmod_tag = ''
            if cast.updated_at:
                lastmod_tag = f'\n    <lastmod>{cast.updated_at.strftime("%Y-%m-%d")}</lastmod>'
            xml_content.append(f'''  <url>
    <loc>{url}</loc>{lastmod_tag}
    <changefreq>weekly</changefreq>
    <priority>0.6</priority>
  </url>''')
        except Exception:
            pass
    
    # ブログ記事
    from ..models.blog import BlogPost
    published_posts = BlogPost.get_published()
    for post in published_posts:
        try:
            url = url_for('public.blog_detail', slug=post.slug, _external=True)
            lastmod_tag = ''
            if post.updated_at:
                lastmod_tag = f'\n    <lastmod>{post.updated_at.strftime("%Y-%m-%d")}</lastmod>'
            xml_content.append(f'''  <url>
    <loc>{url}</loc>{lastmod_tag}
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>''')
        except Exception:
            pass
    
    xml_content.append('</urlset>')
    
    return Response('\n'.join(xml_content), mimetype='application/xml')


@public_bp.route('/robots.txt')
def robots():
    """robots.txt"""
    from flask import Response
    import os
    
    base_url = os.environ.get('BASE_URL', request.url_root.rstrip('/'))
    
    content = f"""User-agent: *
Allow: /
Disallow: /admin/
Disallow: /shop/
Disallow: /auth/
Disallow: /customer/
Disallow: /cast/
Disallow: /api/
Disallow: /webhook/

Sitemap: {base_url}/sitemap.xml
"""
    
    return Response(content, mimetype='text/plain')


@public_bp.route('/google74e3b7f63ee4382f.html')
def google_verification():
    """Google Search Console ownership verification"""
    from flask import Response
    return Response(
        'google-site-verification: google74e3b7f63ee4382f.html',
        mimetype='text/html'
    )


@public_bp.route('/images_db/<path:filename>')
def serve_db_image(filename):
    """データベースから画像データを読み込んで返す (Render対策)"""
    from ..models import ImageStore
    
    image = ImageStore.get_image(filename)
    if not image:
        from flask import abort
        abort(404)
        
    response = make_response(image.data)
    response.headers['Content-Type'] = image.mimetype or 'image/jpeg'
    # キャッシュを1週間有効にする
    response.headers['Cache-Control'] = 'public, max-age=604800'
    return response