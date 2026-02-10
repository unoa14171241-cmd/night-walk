"""Generate app icons from logo image."""
from PIL import Image
import os

# ソース画像
src = 'app/static/icons/IMG_4169.JPG'
icons_dir = 'app/static/icons'

# 画像を開く
img = Image.open(src)

# RGBAに変換（透過対応）
if img.mode != 'RGBA':
    img = img.convert('RGBA')

# 正方形にクロップ（中央）
width, height = img.size
size = min(width, height)
left = (width - size) // 2
top = (height - size) // 2
img = img.crop((left, top, left + size, top + size))

# 各サイズで保存
sizes = [
    ('icon-512.png', 512),
    ('icon-192.png', 192),
    ('apple-touch-icon.png', 180),
    ('favicon-32.png', 32),
]

for filename, px in sizes:
    resized = img.resize((px, px), Image.Resampling.LANCZOS)
    path = os.path.join(icons_dir, filename)
    resized.save(path, 'PNG')
    print(f'Created: {path} ({px}x{px})')

print('Done!')
