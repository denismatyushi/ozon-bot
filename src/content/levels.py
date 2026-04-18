from src.models.content import LevelInfo

LEVELS: dict[str, LevelInfo] = {
    "A1": LevelInfo(
        code="A1",
        name="Beginner · Начальный",
        description=(
            "Вы только начинаете. Познакомитесь с алфавитом, базовыми словами, "
            "научитесь представляться, рассказывать о себе, семье и простых действиях."
        ),
    ),
    "A2": LevelInfo(
        code="A2",
        name="Elementary · Элементарный",
        description=(
            "Вы понимаете простую речь на знакомые темы, можете рассказать о своём дне, "
            "работе и планах. Учите Past Simple, can/must, степени сравнения."
        ),
    ),
    "B1": LevelInfo(
        code="B1",
        name="Intermediate · Средний",
        description=(
            "Вы уверенно говорите на повседневные темы, читаете статьи, "
            "понимаете фильмы с субтитрами. Осваиваете Present Perfect, Future, условные предложения."
        ),
    ),
    "B2": LevelInfo(
        code="B2",
        name="Upper-Intermediate · Выше среднего",
        description=(
            "Вы свободно общаетесь, читаете книги и новости без словаря. "
            "Работаем с пассивным залогом, условными 2/3 типа, косвенной речью."
        ),
    ),
    "C1": LevelInfo(
        code="C1",
        name="Advanced · Продвинутый",
        description=(
            "Вы говорите почти как носитель. Шлифуем идиомы, сложные конструкции, "
            "стилистику и академический английский."
        ),
    ),
}

LEVEL_ORDER = ("A1", "A2", "B1", "B2", "C1")


def next_level(code: str) -> str:
    try:
        i = LEVEL_ORDER.index(code)
        return LEVEL_ORDER[min(i + 1, len(LEVEL_ORDER) - 1)]
    except ValueError:
        return "A1"
