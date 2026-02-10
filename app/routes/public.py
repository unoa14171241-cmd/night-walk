"""
Night-Walk MVP - Public Routes (公開ページ)
"""
from flask import Blueprint, render_template, request, current_app, session, make_response
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
    featured_shops = AdService.get_search_results(featured_only=True)[:6]
    
    # Get recent shops
    recent_shops = Shop.query.filter_by(
        is_published=True, 
        is_active=True
    ).order_by(Shop.created_at.desc()).limit(6).all()
    
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
    if can_show_shifts:
        working_casts = CastShift.get_working_now(shop_id)
    
    # バッジ情報を取得
    shop_badges = AdService.get_shop_badges(shop_id)
    best_badge = AdService.get_best_badge('shop', shop_id)
    
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
    gifts = Gift.get_active_gifts()
    
    # バッジ情報を取得
    cast_badges = AdService.get_cast_badges(cast_id)
    best_badge = AdService.get_best_badge('cast', cast_id)
    
    return render_template('public/cast_detail.html',
                          cast=cast,
                          shop=cast.shop,
                          gifts=gifts,
                          cast_badges=cast_badges,
                          best_badge=best_badge,
                          vacancy_labels=VacancyStatus.STATUS_LABELS,
                          vacancy_colors=VacancyStatus.STATUS_COLORS)


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
                                       'message': message
                                   })
        
        # 店舗を審査待ち状態で作成
        shop = Shop(
            name=shop_name,
            area=area,
            category=category,
            phone=phone,
            review_status=Shop.STATUS_PENDING,
            review_notes=f'担当者: {contact_name}\nメール: {email}\n備考: {message}' if message else f'担当者: {contact_name}\nメール: {email}',
            is_active=False,
            is_published=False
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
        
        # 申込情報を保存（審査完了時のメール送信用）
        shop.review_notes = f'担当者: {contact_name}\nメール: {email}\n仮パスワード: {temp_password}\n備考: {message}' if message else f'担当者: {contact_name}\nメール: {email}\n仮パスワード: {temp_password}'
        
        db.session.commit()
        
        flash('お申し込みありがとうございます！審査完了後、ご登録のメールアドレスにログイン情報をお送りします。', 'success')
        return redirect(url_for('public.shop_apply_complete'))
    
    return render_template('public/shop_apply.html',
                           areas=Shop.AREAS,
                           categories=Shop.CATEGORIES,
                           category_labels=Shop.CATEGORY_LABELS,
                           form_data=None)


@public_bp.route('/apply/complete')
def shop_apply_complete():
    """店舗申込完了ページ"""
    return render_template('public/shop_apply_complete.html')


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
            lastmod = shop.updated_at.strftime('%Y-%m-%d') if shop.updated_at else ''
            xml_content.append(f'''  <url>
    <loc>{url}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>''')
        except Exception:
            pass
    
    # 公開中のキャストページ
    from ..models.gift import Cast
    published_casts = Cast.query.filter_by(is_active=True, is_visible=True).all()
    
    for cast in published_casts:
        # デモ店舗のキャストは除外
        if cast.shop and cast.shop.is_demo:
            continue
        try:
            url = url_for('public.cast_detail', cast_id=cast.id, _external=True)
            xml_content.append(f'''  <url>
    <loc>{url}</loc>
    <changefreq>weekly</changefreq>
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