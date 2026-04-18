"""Spaced-repetition (Leitner) scheduling.

5 boxes. A correct answer promotes the card, a wrong one demotes it back to 1.
Next review is scheduled via the per-box interval.
"""
from datetime import datetime, timedelta

BOX_INTERVALS_HOURS = {
    1: 4,          # same-day quick review
    2: 24,         # next day
    3: 24 * 3,     # 3 days
    4: 24 * 7,     # 1 week
    5: 24 * 21,    # 3 weeks (considered learned)
}

MAX_BOX = 5
MIN_BOX = 1


def next_state(current_box: int, current_streak: int, correct: bool) -> tuple[int, int, datetime]:
    """Return (new_box, new_streak, next_review_at) given the user's answer."""
    if correct:
        new_box = min(current_box + 1, MAX_BOX)
        new_streak = current_streak + 1
    else:
        new_box = MIN_BOX
        new_streak = 0

    hours = BOX_INTERVALS_HOURS[new_box]
    next_at = datetime.utcnow() + timedelta(hours=hours)
    return new_box, new_streak, next_at


def initial_state() -> tuple[int, int, datetime]:
    """State for a freshly introduced word: box 1, due immediately."""
    return 1, 0, datetime.utcnow()
