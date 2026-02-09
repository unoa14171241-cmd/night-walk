"""
Night-Walk - 画像処理サービス
画像の自動リサイズ・最適化機能
"""
import io
import os
from PIL import Image, ImageOps, ExifTags


# 最大画像サイズ（ピクセル）
MAX_IMAGE_SIZE = (1200, 1200)  # 横1200px, 縦1200px

# サムネイルサイズ
THUMBNAIL_SIZE = (400, 400)

# JPEG品質
JPEG_QUALITY = 85

# 最大ファイルサイズ（バイト）
MAX_FILE_SIZE = 500 * 1024  # 500KB


def resize_and_optimize_image(image_file, max_size=MAX_IMAGE_SIZE, quality=JPEG_QUALITY):
    """
    画像をリサイズ・最適化する。
    
    Args:
        image_file: ファイルオブジェクト（werkzeug FileStorage等）
        max_size: 最大サイズ（幅, 高さ）のタプル
        quality: JPEG品質（1-100）
    
    Returns:
        bytes: 最適化された画像データ
        str: 出力フォーマット（'JPEG' or 'PNG'）
    """
    try:
        # 画像を開く
        img = Image.open(image_file)
        
        # EXIF情報に基づいて回転を修正
        img = fix_image_orientation(img)
        
        # RGBに変換（透過PNGの場合は白背景で合成）
        if img.mode in ('RGBA', 'LA', 'P'):
            # 透過がある場合は白背景で合成
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # リサイズ（アスペクト比を維持）
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # バッファに保存
        buffer = io.BytesIO()
        
        # JPEGとして保存（サイズ削減のため）
        img.save(buffer, format='JPEG', quality=quality, optimize=True)
        
        # ファイルサイズが大きすぎる場合は品質を下げて再圧縮
        buffer_size = buffer.tell()
        if buffer_size > MAX_FILE_SIZE:
            for q in [75, 65, 55]:
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=q, optimize=True)
                if buffer.tell() <= MAX_FILE_SIZE:
                    break
        
        buffer.seek(0)
        return buffer.getvalue(), 'JPEG'
        
    except Exception as e:
        print(f"[ERROR] Image processing failed: {e}")
        # エラーの場合は元のファイルをそのまま返す
        image_file.seek(0)
        return image_file.read(), None


def fix_image_orientation(img):
    """
    EXIF情報に基づいて画像の向きを修正する。
    スマホで撮影した画像の回転問題を解決。
    
    Args:
        img: PIL Image object
    
    Returns:
        PIL Image object（回転修正済み）
    """
    try:
        # EXIF情報を取得
        exif = img._getexif()
        if exif is None:
            return img
        
        # Orientation タグを探す
        orientation_key = None
        for key, value in ExifTags.TAGS.items():
            if value == 'Orientation':
                orientation_key = key
                break
        
        if orientation_key is None or orientation_key not in exif:
            return img
        
        orientation = exif[orientation_key]
        
        # 向きに応じて回転・反転
        if orientation == 2:
            img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        elif orientation == 3:
            img = img.rotate(180)
        elif orientation == 4:
            img = img.rotate(180).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        elif orientation == 5:
            img = img.rotate(-90, expand=True).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        elif orientation == 6:
            img = img.rotate(-90, expand=True)
        elif orientation == 7:
            img = img.rotate(90, expand=True).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        elif orientation == 8:
            img = img.rotate(90, expand=True)
        
        return img
        
    except Exception as e:
        print(f"[WARNING] EXIF orientation fix failed: {e}")
        return img


def create_thumbnail(image_data, size=THUMBNAIL_SIZE, quality=80):
    """
    サムネイル画像を生成する。
    
    Args:
        image_data: 画像データ（bytes）
        size: サムネイルサイズ（幅, 高さ）
        quality: JPEG品質
    
    Returns:
        bytes: サムネイル画像データ
    """
    try:
        img = Image.open(io.BytesIO(image_data))
        
        # RGBに変換
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 中央クロップでサムネイル作成
        img = ImageOps.fit(img, size, Image.Resampling.LANCZOS)
        
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=quality, optimize=True)
        buffer.seek(0)
        
        return buffer.getvalue()
        
    except Exception as e:
        print(f"[ERROR] Thumbnail creation failed: {e}")
        return None


def get_image_dimensions(image_file):
    """
    画像のサイズを取得する。
    
    Args:
        image_file: ファイルオブジェクト
    
    Returns:
        tuple: (width, height)
    """
    try:
        img = Image.open(image_file)
        dimensions = img.size
        image_file.seek(0)
        return dimensions
    except Exception:
        return (0, 0)
