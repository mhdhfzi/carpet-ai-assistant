"""Whether the chat is available right now. The widget asks before showing its button, so
customers never meet a chat that can't answer.

The chat is unavailable when:
- the owner switched it off (CHAT_ENABLED=false),
- the AI account ran out of credit (an automatic pause, see `pause`), or
- today's AI reply cap is reached (AI_DAILY_REPLY_LIMIT).
"""

import logging
from datetime import datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import get_settings
from app.db.models import AssistantPause, Message, MessageRole
from app.services.availability import HOURS

logger = logging.getLogger(__name__)

PAUSE_ROW = 1
FIRST_PAUSE = timedelta(minutes=30)
LONGEST_PAUSE = timedelta(hours=6)


def is_available(db: Session) -> bool:
    return get_settings().chat_enabled and paused_until(db) is None and not daily_limit_reached(db)


def paused_until(db: Session) -> datetime | None:
    """The end of the current credit pause, or None if the AI isn't paused."""
    row = db.get(AssistantPause, PAUSE_ROW)
    if row and row.paused_until and row.paused_until > clock.now():
        return row.paused_until
    return None


def pause(db: Session, reason: str) -> datetime:
    """Pause the AI after an out-of-credit error. There is no cheap way to ask the provider
    for the balance, so the pause simply ends and the next customer message is the test:
    if the credit is still gone, the AI pauses again for twice as long (30 min, 1 h, 2 h,
    ... up to 6 h), so few customers ever reach a chat that can't answer."""
    row = db.get(AssistantPause, PAUSE_ROW) or AssistantPause(id=PAUSE_ROW, consecutive=0)
    length = min(FIRST_PAUSE * 2 ** (row.consecutive or 0), LONGEST_PAUSE)
    row.paused_until = clock.now() + length
    row.consecutive = (row.consecutive or 0) + 1
    row.reason = reason[:500]
    db.add(row)
    db.commit()
    logger.error("AI paused until %s: %s", row.paused_until.isoformat(), reason)
    return row.paused_until


def record_success(db: Session) -> None:
    """An AI reply worked: forget earlier pauses (the caller commits)."""
    row = db.get(AssistantPause, PAUSE_ROW)
    if row and (row.consecutive or row.paused_until):
        row.consecutive, row.paused_until, row.reason = 0, None, None


def resume(db: Session) -> None:
    """End a pause straight away, e.g. right after topping up."""
    record_success(db)
    db.commit()


def daily_limit_reached(db: Session) -> bool:
    """Counted in the database, so the cap holds across all server instances. AI replies
    are the assistant messages with a grounded value; fixed replies leave it unset."""
    limit = get_settings().ai_daily_reply_limit
    if limit <= 0:
        return False
    today = clock.now().astimezone(HOURS.timezone).date()
    since = datetime.combine(today, time.min, HOURS.timezone)
    replies = db.scalar(
        select(func.count(Message.id)).where(
            Message.role == MessageRole.ASSISTANT,
            Message.grounded.is_not(None),
            Message.created_at >= since,
        )
    )
    return (replies or 0) >= limit
