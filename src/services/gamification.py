"""XP, ranks and motivational labels — the bot's gamification layer."""

RANKS: list[tuple[int, str]] = [
    (0,     "🌱 Новичок"),
    (50,    "📖 Ученик"),
    (150,   "📚 Студент"),
    (400,   "🎓 Эрудит"),
    (900,   "🏆 Мастер"),
    (2000,  "🌟 Профи"),
    (5000,  "👑 Полиглот"),
]

# XP rewards by action
XP_VOCAB_CORRECT = 5
XP_VOCAB_NEW_LEARNED = 10           # when card reaches box 4
XP_GRAMMAR_EXERCISE_CORRECT = 7
XP_LESSON_COMPLETED_BONUS = 15
XP_PLACEMENT_COMPLETED = 30


def rank_for(total_xp: int) -> str:
    current = RANKS[0][1]
    for threshold, name in RANKS:
        if total_xp >= threshold:
            current = name
        else:
            break
    return current


def next_rank(total_xp: int) -> tuple[str, int] | None:
    """Returns (name, xp_needed_to_reach) or None if already at the top rank."""
    for threshold, name in RANKS:
        if total_xp < threshold:
            return name, threshold - total_xp
    return None
