# app/services/shop_point_service.py
"""店舗スタンプカードサービス"""

import logging
from datetime import datetime, timedelta
from ..extensions import db
from ..models.shop_point import (
    ShopPointCard, CustomerShopPoint, ShopPointTransaction, ShopPointReward
)
from ..models.shop_point_rank import ShopPointRank, CustomerShopRank

logger = logging.getLogger(__name__)


class ShopPointService:
    """店舗スタンプカードに関するビジネスロジック"""
    
    @classmethod
    def get_customer_cards(cls, customer_id):
        """顧客が持っている全店舗のスタンプカード一覧"""
        return CustomerShopPoint.query.filter_by(
            customer_id=customer_id
        ).order_by(CustomerShopPoint.updated_at.desc()).all()
    
    @classmethod
    def get_customer_card(cls, customer_id, shop_id):
        """特定店舗のスタンプカードを取得（なければ作成）"""
        return CustomerShopPoint.get_or_create(customer_id, shop_id)
    
    @classmethod
    def grant_stamp(cls, customer_id, shop_id, verified_by=None, method='manual'):
        """
        スタンプを1つ付与
        
        Args:
            customer_id: 顧客ID
            shop_id: 店舗ID
            verified_by: 確認した店舗スタッフID
            method: 確認方法（'manual', 'qr'）
        
        Returns:
            tuple: (success: bool, message: str, stamps_earned: int)
        """
        card_config = ShopPointCard.get_or_create(shop_id)
        
        if not card_config.is_active:
            return False, 'この店舗ではスタンプカードが有効ではありません', 0
        
        customer_point = CustomerShopPoint.get_or_create(customer_id, shop_id)
        
        # 連続付与チェック
        if not customer_point.can_earn_visit_points(card_config.min_visit_interval_hours):
            next_available = customer_point.last_visit_at + timedelta(hours=card_config.min_visit_interval_hours)
            wait_minutes = int((next_available - datetime.utcnow()).total_seconds() / 60)
            return False, f'次のスタンプ獲得まであと約{wait_minutes}分お待ちください', 0
        
        # スタンプ1つ付与
        stamps = 1
        customer_point.add_points(stamps, reason='visit')
        
        # 取引ログ
        ShopPointTransaction.log_visit(
            customer_id=customer_id,
            shop_id=shop_id,
            points=stamps,
            balance_after=customer_point.point_balance,
            verified_by=verified_by,
            method=method
        )
        
        # ランク昇格チェック（来店回数ベース）
        rank_up_message = ''
        if card_config.rank_system_enabled:
            rank_up_message = cls._check_rank_up(customer_id, shop_id, customer_point)
        
        # スタンプカード完了チェック
        reward_message = ''
        max_stamps = card_config.max_stamps or 10
        current_in_card = customer_point.point_balance % max_stamps
        if current_in_card == 0 and customer_point.point_balance > 0:
            # カード完了！
            reward_message = f'スタンプカードが完了しました！ {card_config.reward_description or "特典をお受け取りください"}' 
        
        db.session.commit()
        
        logger.info(f"Stamp granted: customer={customer_id}, shop={shop_id}, total={customer_point.point_balance}")
        
        msg = f'スタンプを1つ獲得しました！（{current_in_card if current_in_card > 0 else max_stamps}/{max_stamps}）'
        if rank_up_message:
            msg += f' {rank_up_message}'
        if reward_message:
            msg += f' {reward_message}'
        
        return True, msg, stamps
    
    # 後方互換エイリアス
    grant_visit_points = grant_stamp
    
    @classmethod
    def use_reward(cls, customer_id, shop_id, staff_id=None):
        """特典を交換（スタンプを消費）"""
        card_config = ShopPointCard.query.filter_by(shop_id=shop_id).first()
        
        if not card_config or not card_config.is_active:
            return False, 'スタンプカードが有効ではありません', None
        
        if not card_config.reward_description:
            return False, 'この店舗では特典が設定されていません', None
        
        customer_point = CustomerShopPoint.query.filter_by(
            customer_id=customer_id, shop_id=shop_id
        ).first()
        
        if not customer_point:
            return False, 'スタンプがありません', None
        
        max_stamps = card_config.max_stamps or 10
        if customer_point.point_balance < max_stamps:
            return False, f'スタンプが不足しています（必要: {max_stamps}個）', None
        
        try:
            customer_point.use_points(max_stamps)
        except ValueError as e:
            return False, str(e), None
        
        # 特典を発行
        reward = ShopPointReward(
            customer_id=customer_id,
            shop_id=shop_id,
            points_used=max_stamps,
            reward_description=card_config.reward_description,
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        db.session.add(reward)
        
        ShopPointTransaction.log_reward(
            customer_id=customer_id,
            shop_id=shop_id,
            points_used=max_stamps,
            balance_after=customer_point.point_balance,
            reward_description=card_config.reward_description
        )
        
        db.session.commit()
        
        logger.info(f"Reward exchanged: customer={customer_id}, shop={shop_id}")
        return True, '特典を獲得しました！', reward
    
    @classmethod
    def get_customer_rewards(cls, customer_id, shop_id=None, valid_only=True):
        """顧客の特典一覧を取得"""
        query = ShopPointReward.query.filter_by(customer_id=customer_id)
        if shop_id:
            query = query.filter_by(shop_id=shop_id)
        if valid_only:
            query = query.filter_by(status=ShopPointReward.STATUS_PENDING)
        return query.order_by(ShopPointReward.created_at.desc()).all()
    
    @classmethod
    def mark_reward_used(cls, reward_id, staff_id=None):
        """特典を使用済みにする"""
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
        """取引履歴を取得"""
        query = ShopPointTransaction.query.filter_by(customer_id=customer_id)
        if shop_id:
            query = query.filter_by(shop_id=shop_id)
        return query.order_by(ShopPointTransaction.created_at.desc()).limit(limit).all()
    
    @classmethod
    def get_shop_ranking(cls, shop_id, limit=10):
        """店舗のスタンプランキング（累計来店数順）"""
        return CustomerShopPoint.query.filter_by(
            shop_id=shop_id
        ).order_by(CustomerShopPoint.visit_count.desc()).limit(limit).all()

    # =====================
    # ランク関連メソッド
    # =====================

    @classmethod
    def _check_rank_up(cls, customer_id, shop_id, customer_point):
        """ランク昇格チェック（来店回数ベース）"""
        new_rank = ShopPointRank.get_rank_for_visits(shop_id, customer_point.visit_count)
        
        if not new_rank:
            return ''
        
        current_level = 0
        current_rank_entry = CustomerShopRank.get_current_rank(customer_id, shop_id)
        if current_rank_entry:
            current_level = current_rank_entry.rank_level
        
        if new_rank.rank_level <= current_level:
            return ''
        
        if current_rank_entry:
            current_rank_entry.is_current = False
        
        rank_entry = CustomerShopRank(
            customer_id=customer_id,
            shop_id=shop_id,
            rank_id=new_rank.id,
            rank_name=new_rank.rank_name,
            rank_level=new_rank.rank_level,
            rank_icon=new_rank.rank_icon,
            is_current=True
        )
        db.session.add(rank_entry)
        
        customer_point.current_rank_id = new_rank.id
        customer_point.current_rank_name = new_rank.rank_name
        customer_point.current_rank_icon = new_rank.rank_icon
        
        logger.info(f"Rank up: customer={customer_id}, shop={shop_id}, new_rank={new_rank.rank_name}")
        return f'{new_rank.rank_name}ランクに昇格しました！'

    @classmethod
    def get_customer_rank(cls, customer_id, shop_id):
        return CustomerShopRank.get_current_rank(customer_id, shop_id)

    @classmethod
    def get_customer_rank_history(cls, customer_id, shop_id):
        return CustomerShopRank.query.filter_by(
            customer_id=customer_id,
            shop_id=shop_id
        ).order_by(CustomerShopRank.promoted_at.desc()).all()

    @classmethod
    def get_next_rank(cls, customer_id, shop_id):
        """次のランクとそこまでの必要来店回数を返す"""
        customer_point = CustomerShopPoint.query.filter_by(
            customer_id=customer_id, shop_id=shop_id
        ).first()
        
        if not customer_point:
            lowest = ShopPointRank.query.filter_by(shop_id=shop_id).order_by(
                ShopPointRank.rank_level).first()
            return lowest, (lowest.min_total_points if lowest else 0)
        
        current_visits = customer_point.visit_count
        
        next_rank = ShopPointRank.query.filter(
            ShopPointRank.shop_id == shop_id,
            ShopPointRank.min_total_points > current_visits
        ).order_by(ShopPointRank.min_total_points).first()
        
        if not next_rank:
            return None, 0
        
        return next_rank, next_rank.min_total_points - current_visits
