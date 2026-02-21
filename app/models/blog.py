"""Night-Walk - Blog Model"""
from datetime import datetime
from ..extensions import db


class BlogPost(db.Model):
    """ブログ記事"""
    __tablename__ = 'blog_posts'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    title = db.Column(db.String(300), nullable=False)
    excerpt = db.Column(db.String(500))
    content_html = db.Column(db.Text, nullable=False)
    is_published = db.Column(db.Boolean, default=False, index=True)
    published_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get_published(cls):
        return cls.query.filter_by(is_published=True).order_by(cls.published_at.desc()).all()

    @classmethod
    def get_by_slug(cls, slug):
        return cls.query.filter_by(slug=slug, is_published=True).first()

    @classmethod
    def seed_posts(cls):
        """SEO用ダミー記事を生成"""
        if cls.query.first():
            return

        posts = [
            {
                'slug': 'okayama-cabaret-ranking',
                'title': '【2026年最新】岡山おすすめキャバクラ10選｜エリア別に厳選紹介',
                'excerpt': '岡山市内で人気のキャバクラを厳選してご紹介。岡山駅周辺・田町・中央町エリアから、初心者にもおすすめの優良店をピックアップしました。',
                'content_html': '''
<h2>岡山でキャバクラを探すなら</h2>
<p>岡山は中国地方有数のナイトスポットエリア。特に<strong>田町</strong>や<strong>中央町</strong>を中心に、個性豊かなキャバクラが軒を連ねています。</p>
<p>Night-Walkでは、各店舗の空席状況をリアルタイムで確認できるため、「行ってみたら満席だった」という心配がありません。</p>

<h2>エリア別おすすめ店舗</h2>

<h3>岡山駅周辺エリア</h3>
<p>アクセス抜群の岡山駅周辺は、出張や旅行の際にも立ち寄りやすいエリアです。比較的リーズナブルな店舗が多く、初心者の方にもおすすめです。</p>

<h3>田町・中央町エリア</h3>
<p>岡山最大の歓楽街である田町・中央町エリアは、高級店からカジュアル店まで幅広いラインナップが魅力です。キャストのレベルも高く、特別な夜を過ごしたい方におすすめです。</p>

<h3>倉敷エリア</h3>
<p>美観地区で有名な倉敷にも、知る人ぞ知る名店が点在しています。岡山市内とはまた違った雰囲気を楽しめます。</p>

<h2>失敗しないキャバクラ選びのポイント</h2>
<ul>
<li><strong>料金体系の確認</strong> - セット料金、ドリンク代、延長料金を事前にチェック</li>
<li><strong>口コミをチェック</strong> - Night-Walkの口コミ機能で実際の評判を確認</li>
<li><strong>空席状況の確認</strong> - リアルタイムの空席情報で無駄足を回避</li>
<li><strong>キャストのプロフィール</strong> - 事前にキャスト情報を確認して好みの店舗を見つける</li>
</ul>

<h2>まとめ</h2>
<p>岡山には魅力的なキャバクラがたくさんあります。Night-Walkを活用して、あなたにぴったりのお店を見つけてください。空席状況のリアルタイム確認、キャストランキング、口コミ情報など、便利な機能をぜひご活用ください。</p>
'''
            },
            {
                'slug': 'okayama-night-work-guide',
                'title': '岡山で稼げる夜職ガイド｜キャバクラ・ガールズバーの給与相場と選び方',
                'excerpt': '岡山で夜職を始めたい方向けの完全ガイド。キャバクラやガールズバーの給与相場、働きやすいお店の選び方、面接のポイントまで詳しく解説します。',
                'content_html': '''
<h2>岡山の夜職マーケット</h2>
<p>岡山は中国・四国地方の中核都市として、ナイトワーク業界も活気があります。特に<strong>田町</strong>や<strong>中央町</strong>のエリアを中心に、多くの店舗が人材を募集しています。</p>

<h2>業態別の給与相場</h2>

<h3>キャバクラ</h3>
<p>岡山のキャバクラの時給相場は<strong>3,000円〜5,000円</strong>が一般的です。経験者やルックスに自信のある方は、さらに高い時給を提示されることもあります。加えてドリンクバックや指名料なども収入源になります。</p>

<h3>ガールズバー</h3>
<p>ガールズバーの時給相場は<strong>1,800円〜3,000円</strong>程度。キャバクラと比べるとカジュアルな接客スタイルで、ドレスアップの必要が少ないため、初心者の方も始めやすい環境です。</p>

<h3>ラウンジ・スナック</h3>
<p>落ち着いた雰囲気のラウンジやスナックは時給<strong>2,000円〜4,000円</strong>が目安。常連のお客様との会話が中心で、長く安定して働ける環境が整っています。</p>

<h2>働きやすいお店の見分け方</h2>
<ul>
<li><strong>体入制度がある</strong> - 実際に働いてから判断できるお店は信頼できます</li>
<li><strong>送迎制度</strong> - 終電後の帰宅手段が確保されているか確認しましょう</li>
<li><strong>ノルマの有無</strong> - 初心者はノルマなしのお店がおすすめ</li>
<li><strong>スタッフの対応</strong> - 面接時のスタッフの雰囲気で職場環境がわかります</li>
</ul>

<h2>Night-Walkで求人を探す</h2>
<p>Night-Walkでは求人情報も掲載しています。「求人あり」のバッジがついた店舗をチェックして、あなたに合ったお店を見つけてください。店舗の口コミやキャスト情報も参考にできます。</p>
'''
            },
            {
                'slug': 'nightlife-beginners-guide',
                'title': '夜職初心者向け完全ガイド｜キャバクラ・ガールズバーの楽しみ方',
                'excerpt': 'キャバクラやガールズバーに初めて行く方向けの完全ガイド。マナー、料金の仕組み、楽しみ方のコツまで丁寧に解説します。',
                'content_html': '''
<h2>はじめてのナイトスポット</h2>
<p>キャバクラやガールズバーに興味はあるけれど、「どんな場所かわからない」「料金が不安」という方は多いのではないでしょうか。この記事では、初めての方でも安心して楽しめるよう、基本的な知識をお伝えします。</p>

<h2>業態の違いを知ろう</h2>

<h3>キャバクラ</h3>
<p>キャストが隣に座って接客してくれるスタイル。華やかな雰囲気で、特別な時間を過ごせます。セット料金制が一般的で、60分5,000円〜10,000円程度が相場です。</p>

<h3>ガールズバー</h3>
<p>カウンター越しにキャストと会話を楽しむスタイル。カジュアルな雰囲気で、一人でも気軽に入れます。1ドリンク制や時間制など、お店によってシステムが異なります。</p>

<h3>スナック</h3>
<p>ママやスタッフとの会話を楽しむアットホームなスタイル。常連さんが多く、地域の社交場としての役割もあります。料金はリーズナブルで、3,000円〜5,000円程度で楽しめるお店が多いです。</p>

<h2>基本的なマナー</h2>
<ul>
<li><strong>予算を決めておく</strong> - 事前に使える金額を決めて、無理のない範囲で楽しみましょう</li>
<li><strong>キャストへの配慮</strong> - 過度なボディタッチやしつこい連絡先交換は控えましょう</li>
<li><strong>飲みすぎに注意</strong> - 楽しい雰囲気でつい飲みすぎてしまいがちですが、適度に</li>
<li><strong>会計の確認</strong> - 不明な点は入店時に確認。明朗会計のお店を選びましょう</li>
</ul>

<h2>Night-Walkを活用しよう</h2>
<p>Night-Walkなら、<strong>空席状況のリアルタイム確認</strong>、<strong>キャストのプロフィール閲覧</strong>、<strong>口コミチェック</strong>が可能です。初めてのお店選びも安心。まずはNight-Walkで気になるお店を探してみませんか？</p>
'''
            },
        ]

        for data in posts:
            post = cls(
                slug=data['slug'],
                title=data['title'],
                excerpt=data['excerpt'],
                content_html=data['content_html'],
                is_published=True,
                published_at=datetime.utcnow(),
            )
            db.session.add(post)

        db.session.commit()
