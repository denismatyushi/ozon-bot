"""Helpers for building quiz questions at runtime."""
import random

from src.content.vocabulary import Word, words_for_level


def build_translation_choices(
    target: Word,
    direction: str = "en_to_ru",
    pool_level: str | None = None,
    num_distractors: int = 3,
) -> tuple[list[str], int]:
    """Return (options, correct_index) for a multiple choice translation task.

    direction:
        "en_to_ru" — prompt is EN word, options are RU translations.
        "ru_to_en" — prompt is RU word, options are EN words.
    """
    level = pool_level or target.level
    pool = [w for w in words_for_level(level) if w.id != target.id]
    if len(pool) < num_distractors:
        # fall back to other levels to fill distractors
        from src.content.vocabulary import ALL_WORDS
        pool = [w for w in ALL_WORDS if w.id != target.id]

    distractors = random.sample(pool, num_distractors)
    if direction == "en_to_ru":
        options = [target.ru] + [d.ru for d in distractors]
    else:
        options = [target.en] + [d.en for d in distractors]

    indices = list(range(len(options)))
    random.shuffle(indices)
    shuffled = [options[i] for i in indices]
    correct_idx = indices.index(0)
    return shuffled, correct_idx
