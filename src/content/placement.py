"""Placement test — 15 questions, 3 per level from A1..C1.

We infer student's level by finding the highest level where they answered
at least 2 of 3 questions correctly. If everything fails, we place them at A1.
"""
from src.models.content import PlacementQuestion


def _q(level: str, prompt: str, options: list[str], correct: int, explanation: str = "") -> PlacementQuestion:
    return PlacementQuestion(level=level, prompt=prompt, options=tuple(options), correct=correct, explanation=explanation)


QUESTIONS: list[PlacementQuestion] = [
    # A1
    _q("A1", "Hello, my name ___ Anna.", ["am", "is", "are", "be"], 1, "name (it) → is."),
    _q("A1", "I ___ a sandwich for breakfast every day.", ["eats", "eat", "eating", "ate"], 1, "I + инфинитив без -s."),
    _q("A1", "She has two ___ and one brother.", ["sister", "sisters", "sisteres", "sisters's"], 1, "Мн. число — sisters."),

    # A2
    _q("A2", "We ___ to Paris last summer.", ["go", "went", "goes", "going"], 1, "last summer → Past Simple."),
    _q("A2", "This test is ___ than the previous one.", ["easy", "easier", "more easy", "easiest"], 1, "Короткое прилагательное → +er."),
    _q("A2", "You ___ stop at a red light — it's the law.", ["can", "should", "must", "may"], 2, "Обязанность → must."),

    # B1
    _q("B1", "I ___ in this city for five years.", ["live", "lived", "have lived", "am living"], 2, "Длительное действие до настоящего → Present Perfect."),
    _q("B1", "If it rains tomorrow, we ___ the picnic.", ["cancel", "will cancel", "cancelled", "would cancel"], 1, "Условное 1 типа → will + V."),
    _q("B1", "She's tired ___ she worked 12 hours today.", ["so", "because", "although", "but"], 1, "Причина → because."),

    # B2
    _q("B2", "The report ___ by the end of this week.", ["will finish", "will be finished", "finishes", "has finished"], 1, "Future Passive → will be + V3."),
    _q("B2", "If I ___ you, I would apologise.", ["am", "was", "were", "had been"], 2, "Условное 2 типа → were."),
    _q("B2", "He said he ___ the email the day before.", ["sends", "sent", "had sent", "has sent"], 2, "Косвенная речь: Past Simple → Past Perfect."),

    # C1
    _q("C1", "Not only ___ late, but he also forgot his passport.", ["he was", "was he", "he is", "is he"], 1, "Инверсия после not only."),
    _q("C1", "I wish I ___ that decision last year.", ["don't make", "didn't make", "hadn't made", "wouldn't make"], 2, "Сожаление о прошлом → had not made."),
    _q("C1", "The project was approved despite ___ over budget.", ["it was", "being", "to be", "it had been"], 1, "despite + герундий."),
]


def level_from_results(answers: list[bool]) -> str:
    """Return the highest level with >=2/3 correct; default A1.

    answers are in the same order as QUESTIONS.
    """
    by_level: dict[str, tuple[int, int]] = {}
    for q, ok in zip(QUESTIONS, answers):
        correct, total = by_level.get(q.level, (0, 0))
        by_level[q.level] = (correct + (1 if ok else 0), total + 1)

    level = "A1"
    for code in ("A1", "A2", "B1", "B2", "C1"):
        c, t = by_level.get(code, (0, 0))
        if t and c >= max(2, (t * 2) // 3):
            level = code
        else:
            break  # stop at first level the student doesn't master
    return level
