"""Generate default OGP image from logo."""
from PIL import Image, ImageDraw
import os

# OGP推奨サイズ
OGP_WIDTH = 1200
OGP_HEIGHT = 630

# 背景色（Night-Walkのダークテーマ）
BG_COLOR = (11, 11, 24)  # #0B0B18

# 出力パス
output_path = 'app/static/images/ogp-default.png'

# ロゴ画像
logo_path = 'app/static/icons/IMG_4169.JPG'

# OGP画像を作成
img = Image.new('RGB', (OGP_WIDTH, OGP_HEIGHT), BG_COLOR)

# ロゴを配置
if os.path.exists(logo_path):
    logo = Image.open(logo_path)
    
    # RGBAに変換
    if logo.mode != 'RGBA':
        logo = logo.convert('RGBA')
    
    # ロゴを適切なサイズにリサイズ（高さの60%程度）
    logo_height = int(OGP_HEIGHT * 0.6)
    logo_ratio = logo.width / logo.height
    logo_width = int(logo_height * logo_ratio)
    logo = logo.resize((logo_width, logo_height), Image.Resampling.LANCZOS)
    
    # 中央に配置
    x = (OGP_WIDTH - logo_width) // 2
    y = (OGP_HEIGHT - logo_height) // 2
    
    # 背景画像にロゴを貼り付け
    img.paste(logo, (x, y), logo if logo.mode == 'RGBA' else None)

# 保存
img.save(output_path, 'PNG')
print(f'Created: {output_path} ({OGP_WIDTH}x{OGP_HEIGHT})')
