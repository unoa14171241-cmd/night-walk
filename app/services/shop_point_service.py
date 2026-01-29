# app/services/shop_point_service.py
"""店舗ポイントカードサービス"""

import logging
from datetime import datetime, timedelta
from ..extensions import db
from ..models.shop_point import (
    ShopPointCard, CustomerShopPoint, ShopPointTransaction, ShopPointReward
)

logger = logging.getLogger(__name__)


class ShopPointService:
    """店舗ポイントカードに関するビジネスロジック"""
    
    @classmethod
    def get_customer_cards(cls, customer_id):
        """
        顧客が持っている全店舗のポイントカード一覧を取得
        
        Returns:
            list: CustomerShopPoint リスト（ポイント残高順）
        """
        return CustomerShopPoint.query.filter_by(
            customer_id=customer_id
        ).order_by(CustomerShopPoint.point_balance.desc()).all()
    
    @classmethod
    def get_customer_card(cls, customer_id, shop_id):
        """
        特定店舗のポイントカードを取得（なければ作成）
        
        Returns:
            CustomerShopPoint
        """
        return CustomerShopPoint.get_or_create(customer_id, shop_id)
    
    @classmethod
    def grant_visit_points(cls, customer_id, shop_id, verified_by=None, method='manual'):
        """
        来店ポイントを付与
        
        Args:
            customer_id: 顧客ID
            shop_id: 店舗ID
            verified_by: 確認した店舗スタッフID
            method: 確認方法（'manual', 'qr', 'checkin'）
        
        Returns:
            tuple: (success: bool, message: str, points_earned: int)
        """
        # ポイントカード設定を取得
        card_config = ShopPointCard.get_or_create(shop_id)
        
        if not card_config.is_active:
            return False, 'この店舗ではポイントカードが有効ではありません', 0
        
        # 顧客のポイント残高を取得
        customer_point = CustomerShopPoint.get_or_create(customer_id, shop_id)
        
        # 連続付与チェック
        if not customer_point.can_earn_visit_points(card_config.min_visit_interval_hours):
            next_available = customer_point.last_visit_at + timedelta(hours=card_config.min_visit_interval_hours)
            wait_minutes = int((next_available - datetime.utcnow()).total_seconds() / 60)
            return False, f'次のポイント獲得まであと約{wait_minutes}分お待ちください', 0
        
        # ポイント付与
        points = card_config.visit_points
        customer_point.add_points(points, reason='visit')
        
        # 取引ログ
        ShopPointTransaction.log_visit(
            customer_id=customer_id,
            shop_id=shop_id,
            points=points,
            balance_after=customer_point.point_balance,
            verified_by=verified_by,
            method=method
        )
        
        db.session.commit()
        
        logger.info(f"Visit points granted: customer={customer_id}, shop={shop_id}, points={points}")
        
        return True, f'{points}ポイントを獲得しました！', points
    
    @classmethod
    def use_reward(cls, customer_id, shop_id, staff_id=None):
        """
        特典を交換（ポイントを使用）
        
        Returns:
            tuple: (success: bool, message: str, reward: ShopPointReward or None)
        """
        # ポイントカード設定を取得
        card_config = ShopPointCard.query.filter_by(shop_id=shop_id).first()
        
        if not card_config or not card_config.is_active:
            return False, 'ポイントカードが有効ではありません', None
        
        if not card_config.reward_description:
            return False, 'この店舗では特典が設定されていません', None
        
        # 顧客のポイント残高を確認
        customer_point = CustomerShopPoint.query.filter_by(
            customer_id=customer_id, shop_id=shop_id
        ).first()
        
        if not customer_point:
            return False, 'ポイントがありません', None
        
        if customer_point.point_balance < card_config.reward_threshold:
            return False, f'ポイントが不足しています（必要: {card_config.reward_threshold}pt）', None
        
        # ポイント消費
        try:
            customer_point.use_points(card_config.reward_threshold)
        except ValueError as e:
            return False, str(e), None
        
        # 特典を発行
        reward = ShopPointReward(
            customer_id=customer_id,
            shop_id=shop_id,
            points_used=card_config.reward_threshold,
            reward_description=card_config.reward_description,
            expires_at=datetime.utcnow() + timedelta(days=30)  # 30日間有効
        )
        db.session.add(reward)
        
        # 取引ログ
        ShopPointTransaction.log_reward(
            customer_id=customer_id,
            shop_id=shop_id,
            points_used=card_config.reward_threshold,
            balance_after=customer_point.point_balance,
            reward_description=card_config.reward_description
        )
        
        db.session.commit()
        
        logger.info(f"Reward exchanged: customer={customer_id}, shop={shop_id}")
        
        return True, '特典を獲得しました！', reward
    
    @classmethod
    def get_customer_rewards(cls, customer_id, shop_id=None, valid_only=True):
        """
        顧客の特典一覧を取得
        
        Args:
            customer_id: 顧客ID
            shop_id: 店舗ID（Noneの場合は全店舗）
            valid_only: 有効な特典のみ
        
        Returns:
            list: ShopPointReward リスト
        """
        query = ShopPointReward.query.filter_by(customer_id=customer_id)
        
        if shop_id:
            query = query.filter_by(shop_id=shop_id)
        
        if valid_only:
            query = query.filter_by(status=ShopPointReward.STATUS_PENDING)
        
        return query.order_by(ShopPointReward.created_at.desc()).all()
    
    @classmethod
    def mark_reward_used(cls, reward_id, staff_id=None):
        """
        特典を使用済みにする（店舗スタッフが確認）
        
        Returns:
            tuple: (success: bool, message: str)
        """
        reward = ShopPointReward.query.get(reward_id)
        
        if not reward:
            return False, '特典が見つかりません'
        
        if not reward.is_valid:
            return False, '既に使用済みまたは期限切れです'
        
        reward.mark_as_used(staff_id)
        db.session.commit()
        
        return True, '特典を使用しました'
    
    @classmethod
    def get_transaction_history(cls, customer_id, shop_id=None, limit=50):
        """
        取引履歴を取得
        
        Returns:
            list: ShopPointTransaction リスト
        """
        query = ShopPointTransaction.query.filter_by(customer_id=customer_id)
        
        if shop_id:
            query = query.filter_by(shop_id=shop_id)
        
        return query.order_by(ShopPointTransaction.created_at.desc()).limit(limit).all()
    
    @classmethod
    def get_shop_ranking(cls, shop_id, limit=10):
        """
        店舗のポイントランキング（累計獲得ポイント順）
        
        Returns:
            list: CustomerShopPoint リスト
        """
        return CustomerShopPoint.query.filter_by(
            shop_id=shop_id
        ).order_by(CustomerShopPoint.total_earned.desc()).limit(limit).all()
