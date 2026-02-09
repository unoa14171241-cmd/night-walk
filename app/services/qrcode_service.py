"""
Night-Walk - QRコード生成サービス
名刺・営業資料用のQRコード生成機能
"""
import io
import base64
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
from PIL import Image


def generate_qrcode(url, size=10, border=2):
    """
    QRコードを生成する。
    
    Args:
        url: エンコードするURL
        size: ボックスサイズ（デフォルト: 10）
        border: ボーダーサイズ（デフォルト: 2）
    
    Returns:
        PIL Image object
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # 高い誤り訂正レベル
        box_size=size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    # スタイリッシュなQRコード（角丸）
    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer()
    )
    
    return img


def generate_qrcode_png(url, size=10, border=2, high_res=False):
    """
    PNG形式でQRコードを生成する。
    
    Args:
        url: エンコードするURL
        size: ボックスサイズ
        border: ボーダーサイズ
        high_res: 高解像度（名刺印刷用）
    
    Returns:
        bytes: PNG画像データ
    """
    # 高解像度の場合はサイズを大きくする
    if high_res:
        size = 20  # 高解像度用
    
    img = generate_qrcode(url, size=size, border=border)
    
    # RGBに変換（PNGとして保存するため）
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG', quality=100)
    buffer.seek(0)
    
    return buffer.getvalue()


def generate_qrcode_svg(url, border=2):
    """
    SVG形式でQRコードを生成する。
    
    Args:
        url: エンコードするURL
        border: ボーダーサイズ
    
    Returns:
        str: SVG文字列
    """
    import qrcode.image.svg
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    # SVG形式で生成
    factory = qrcode.image.svg.SvgPathImage
    img = qr.make_image(image_factory=factory)
    
    buffer = io.BytesIO()
    img.save(buffer)
    buffer.seek(0)
    
    return buffer.getvalue().decode('utf-8')


def generate_qrcode_base64(url, size=10, border=2):
    """
    Base64エンコードされたPNG QRコードを生成する。
    HTMLでの表示用。
    
    Args:
        url: エンコードするURL
        size: ボックスサイズ
        border: ボーダーサイズ
    
    Returns:
        str: Base64エンコードされた画像データ
    """
    png_data = generate_qrcode_png(url, size=size, border=border)
    return base64.b64encode(png_data).decode('utf-8')
