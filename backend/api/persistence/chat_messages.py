"""
消息持久化辅助函数

职责：
- 保存用户消息到数据库
- 保存助手回复到数据库
"""

import logging
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from infra.database import DatabaseManager

logger = logging.getLogger(__name__)


def save_user_message(
    db: "DatabaseManager",
    session_id: str,
    content: str,
) -> Optional[int]:
    """
    保存用户消息

    Args:
        db: 数据库管理器
        session_id: 会话 ID
        content: 消息内容

    Returns:
        消息 ID，失败返回 None
    """
    try:
        message_id = db.save_chat_message(
            session_id=session_id,
            role="user",
            content=content,
            message_type="text",
        )
        logger.debug(f"[Chat] 保存用户消息成功: session={session_id}, message_id={message_id}")
        return message_id
    except Exception as e:
        logger.error(f"[Chat] 保存用户消息失败: session={session_id}, error={e}")
        return None


def save_assistant_message(
    db: "DatabaseManager",
    session_id: str,
    content: str,
    thinking: Optional[str] = None,
    steps: Optional[List[dict]] = None,
) -> Optional[int]:
    """
    保存助手回复

    Args:
        db: 数据库管理器
        session_id: 会话 ID
        content: 回复内容
        thinking: 思考过程（可选）
        steps: 执行步骤（可选）

    Returns:
        消息 ID，失败返回 None
    """
    if not content:
        logger.warning(f"[Chat] 助手回复内容为空，跳过保存: session={session_id}")
        return None

    try:
        message_id = db.save_chat_message(
            session_id=session_id,
            role="assistant",
            content=content,
            message_type="answer",
            thinking=thinking or None,
            steps=steps,
        )
        logger.info(
            f"[Chat] 保存助手回复成功: session={session_id}, "
            f"message_id={message_id}, content_len={len(content)}"
        )
        return message_id
    except Exception as e:
        logger.error(f"[Chat] 保存助手回复失败: session={session_id}, error={e}")
        return None


__all__ = ["save_user_message", "save_assistant_message"]
