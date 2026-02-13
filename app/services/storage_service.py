"""
Night-Walk - クラウドストレージサービス
画像をCloudinary（本番）またはローカルファイルシステム（開発）に保存する。
デプロイ時に画像がリセットされる問題を解決。
"""
import os
import io
import uuid
from flask import current_app, url_for


def _get_cloudinary():
    """Cloudinaryを初期化して返す"""
    import cloudinary
    import cloudinary.uploader
    import cloudinary.api
    
    cloudinary.config(
        cloud_name=current_app.config.get('CLOUDINARY_CLOUD_NAME'),
        api_key=current_app.config.get('CLOUDINARY_API_KEY'),
        api_secret=current_app.config.get('CLOUDINARY_API_SECRET'),
        secure=True
    )
    return cloudinary, cloudinary.uploader


def is_cloud_storage_enabled():
    """クラウドストレージが有効かどうか"""
    return bool(current_app.config.get('USE_CLOUD_STORAGE'))


def upload_image(file_data, folder, filename_prefix='', optimize=True):
    """
    画像をアップロードする。
    Cloudinaryが設定されていればクラウドに、なければローカルに保存。
    
    Args:
        file_data: ファイルオブジェクト（werkzeug FileStorage）またはbytesデータ
        folder: サブフォルダ名（'shops', 'casts', 'ads', 'gifts'）
        filename_prefix: ファイル名のプレフィックス
        optimize: 画像を最適化するかどうか
    
    Returns:
        dict: {
            'filename': str,  # ローカルファイル名またはCloudinary public_id
            'url': str,       # 画像のURL
            'storage': str,   # 'local' or 'cloudinary'
        }
        or None on failure
    """
    if is_cloud_storage_enabled():
        return _upload_to_cloudinary(file_data, folder, filename_prefix)
    else:
        return _upload_to_local(file_data, folder, filename_prefix)


def _upload_to_cloudinary(file_data, folder, filename_prefix=''):
    """Cloudinaryにアップロード"""
    try:
        cloudinary, uploader = _get_cloudinary()
        
        # public_idを生成
        unique_id = uuid.uuid4().hex[:8]
        public_id = f"night-walk/{folder}/{filename_prefix}{unique_id}"
        
        # ファイルデータの準備
        if isinstance(file_data, bytes):
            upload_data = io.BytesIO(file_data)
        elif hasattr(file_data, 'read'):
            # FileStorageオブジェクト
            file_data.seek(0)
            upload_data = file_data
        else:
            return None
        
        # Cloudinaryにアップロード
        result = uploader.upload(
            upload_data,
            public_id=public_id,
            folder=None,  # public_idにフォルダを含めている
            resource_type='image',
            overwrite=True,
            transformation=[
                {'width': 1200, 'height': 1200, 'crop': 'limit'},
                {'quality': 'auto', 'fetch_format': 'auto'}
            ]
        )
        
        return {
            'filename': result['public_id'],
            'url': result['secure_url'],
            'storage': 'cloudinary'
        }
    except Exception as e:
        current_app.logger.error(f"Cloudinary upload failed: {e}", exc_info=True)
        # フォールバック: ローカルに保存
        return _upload_to_local(file_data, folder, filename_prefix)


def _upload_to_local(file_data, folder, filename_prefix=''):
    """ローカルファイルシステムに保存"""
    try:
        unique_id = uuid.uuid4().hex[:8]
        ext = 'jpg'  # デフォルト
        
        # ファイル名から拡張子を取得
        if hasattr(file_data, 'filename') and file_data.filename:
            parts = file_data.filename.rsplit('.', 1)
            if len(parts) > 1:
                ext = parts[1].lower()
        
        filename = f"{filename_prefix}{unique_id}.{ext}"
        
        # ディレクトリ作成
        upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', folder)
        os.makedirs(upload_dir, exist_ok=True)
        
        filepath = os.path.join(upload_dir, filename)
        
        # 保存
        if isinstance(file_data, bytes):
            with open(filepath, 'wb') as f:
                f.write(file_data)
        elif hasattr(file_data, 'save'):
            file_data.seek(0)
            file_data.save(filepath)
        elif hasattr(file_data, 'read'):
            file_data.seek(0)
            with open(filepath, 'wb') as f:
                f.write(file_data.read())
        
        return {
            'filename': filename,
            'url': f'/static/uploads/{folder}/{filename}',
            'storage': 'local'
        }
    except Exception as e:
        current_app.logger.error(f"Local upload failed: {e}", exc_info=True)
        return None


def delete_image(filename, folder):
    """
    画像を削除する。
    
    Args:
        filename: ファイル名またはCloudinary public_id
        folder: サブフォルダ名
    """
    if not filename:
        return
    
    # Cloudinaryのpublic_idかどうかを判定
    if '/' in filename or is_cloud_storage_enabled():
        _delete_from_cloudinary(filename)
    else:
        _delete_from_local(filename, folder)


def _delete_from_cloudinary(public_id):
    """Cloudinaryから削除"""
    try:
        cloudinary, uploader = _get_cloudinary()
        uploader.destroy(public_id, resource_type='image')
        current_app.logger.info(f"Cloudinary image deleted: {public_id}")
    except Exception as e:
        current_app.logger.warning(f"Cloudinary delete failed for {public_id}: {e}")


def _delete_from_local(filename, folder):
    """ローカルファイルを削除"""
    try:
        filepath = os.path.join(current_app.root_path, 'static', 'uploads', folder, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            current_app.logger.info(f"Local image deleted: {filepath}")
    except Exception as e:
        current_app.logger.warning(f"Local delete failed for {filename}: {e}")


def get_image_url(filename, folder):
    """
    画像のURLを取得する。
    
    Args:
        filename: ファイル名またはCloudinary public_id
        folder: サブフォルダ名（'shops', 'casts', 'ads', 'gifts'）
    
    Returns:
        str: 画像のURL
    """
    if not filename:
        return None
    
    # Cloudinaryのpublic_id形式（night-walk/shops/xxx）の場合
    if filename.startswith('night-walk/') or filename.startswith('http'):
        if filename.startswith('http'):
            return filename
        # Cloudinary URLを構築
        cloud_name = current_app.config.get('CLOUDINARY_CLOUD_NAME')
        if cloud_name:
            return f"https://res.cloudinary.com/{cloud_name}/image/upload/{filename}"
        # フォールバック
        return f'/static/uploads/{folder}/{filename}'
    
    # ローカルファイルパス
    return f'/static/uploads/{folder}/{filename}'
