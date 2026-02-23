# Night-Walk MVP

岡山・倉敷エリアのナイトレジャー業界向けバーティカルSaaS

## 概要

Night-Walkは、ナイトレジャー店舗向けの統合管理システムです。MVPでは以下の機能を提供します：

- **空席ステータスの即時共有** - 店舗の空き状況をリアルタイムで公開
- **電話予約の自動化** - Twilioを使った自動音声予約システム
- **店舗情報管理** - 店舗詳細、営業時間、料金目安の管理
- **求人管理** - 求人情報の掲載・管理
- **課金管理** - Stripeによるサブスクリプション管理

### 営業時間表示ポリシー（コンプライアンス）

- 風営法等の観点から、**公開画面は終了時刻を表示せず `開始時刻〜LAST` で統一**します。
- 管理画面・集計では `open_time` / `close_time` の**実時間を内部保持**して運用します。

## 技術スタック

- **Backend**: Python 3.10+ / Flask / Flask-Login
- **Database**: PostgreSQL (開発時はSQLite)
- **Frontend**: Jinja2 + HTML/CSS/JS (レスポンシブ)
- **External APIs**: Twilio (電話予約), Stripe (課金)
- **Scheduler**: APScheduler

## セットアップ

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd night-walk
```

### 2. 仮想環境の作成

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 4. 環境変数の設定

```bash
# env.example を .env にコピー
copy env.example .env  # Windows
cp env.example .env    # Mac/Linux

# .env を編集して必要な値を設定
```

### 5. データベースの初期化

```bash
# 開発用シードデータの投入
python scripts/seed.py
```

### 6. アプリケーションの起動

```bash
python run.py
```

ブラウザで http://localhost:5000 にアクセス

## 開発用アカウント

| 役割 | メール | パスワード |
|------|--------|-----------|
| 管理者 | admin@night-walk.jp | admin123 |
| オーナー | owner@example.com | owner123 |
| スタッフ | staff@example.com | staff123 |

## 画面構成

### 管理側（店舗・運営）
1. ログイン (`/auth/login`)
2. ダッシュボード (`/shop/`)
3. 空席ステータス更新 (`/shop/vacancy`)
4. 店舗情報編集 (`/shop/edit`)
5. 求人管理 (`/shop/jobs`)

### ユーザー側（来店客）
6. 店舗一覧 (`/`)
7. 店舗詳細 (`/shops/<id>`)
8. 予約導線 (`/shops/<id>/booking`)

### 運営管理
- 運営ダッシュボード (`/admin/`)
- 店舗管理 (`/admin/shops`)
- ユーザー管理 (`/admin/users`)
- 課金状況 (`/admin/billing`)
- 監査ログ (`/admin/audit`)

## API エンドポイント

| Method | URL | 説明 |
|--------|-----|------|
| GET | `/api/vacancy/<shop_id>` | 空席ステータス取得 |
| POST | `/api/vacancy/<shop_id>` | 空席ステータス更新 |
| GET | `/api/shops` | 店舗一覧(JSON) |

## Webhook

| URL | サービス | 説明 |
|-----|----------|------|
| `/webhook/stripe` | Stripe | 課金イベント |
| `/webhook/twilio/voice` | Twilio | 音声コールバック |
| `/webhook/twilio/status` | Twilio | ステータスコールバック |

## 権限（RBAC）

| 権限 | admin | owner | staff |
|------|-------|-------|-------|
| 空席更新 | ✓ | ✓ | ✓ |
| 店舗編集 | ✓ | ✓ | - |
| 求人管理 | ✓ | ✓ | - |
| 課金確認 | ✓ | ✓ | - |
| 運営管理 | ✓ | - | - |

## デプロイ (Render)

1. Renderでアカウント作成
2. PostgreSQLデータベースを作成
3. Web Serviceを作成
4. 環境変数を設定:
   - `DATABASE_URL`: PostgreSQL接続URL
   - `SECRET_KEY`: ランダムな文字列
   - `FLASK_ENV`: production
   - その他必要なAPI キー

## ライセンス

Proprietary - All rights reserved.
