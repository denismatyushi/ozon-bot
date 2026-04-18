"""Grammar lessons grouped by CEFR level.

Each lesson has a short theory section (Markdown-safe, no HTML tags) and a
few multiple-choice exercises.
"""
from src.models.content import Exercise, GrammarLesson


def _e(prompt: str, options: list[str], correct: int, explanation: str = "") -> Exercise:
    return Exercise(prompt=prompt, options=tuple(options), correct=correct, explanation=explanation)


LESSONS: list[GrammarLesson] = [
    # ───────────── A1 ─────────────
    GrammarLesson(
        id="A1:verb-to-be",
        level="A1",
        title="Глагол to be (am / is / are)",
        summary="Самый первый кирпичик английского: как сказать «я — студент», «она — дома».",
        theory=(
            "Глагол *to be* переводится как «быть» / «являться» и никогда не опускается в предложении.\n\n"
            "• I **am** a student.\n"
            "• He / She / It **is** tired.\n"
            "• We / You / They **are** happy.\n\n"
            "Отрицание: add **not** → I am not, he is not (isn't), they are not (aren't).\n"
            "Вопрос: ставим *be* в начало → **Are** you ready?"
        ),
        exercises=(
            _e("She ___ my sister.", ["am", "is", "are", "be"], 1, "He/She/It → is."),
            _e("They ___ at home now.", ["am", "is", "are", "been"], 2, "They → are."),
            _e("I ___ not hungry.", ["am", "is", "are", "do"], 0, "I → am."),
            _e("___ you a teacher?", ["Am", "Is", "Are", "Do"], 2, "В вопросе с you используем Are."),
        ),
    ),
    GrammarLesson(
        id="A1:present-simple",
        level="A1",
        title="Present Simple",
        summary="Говорим о привычках и повседневных действиях.",
        theory=(
            "Используем для регулярных действий, фактов и привычек.\n\n"
            "• I / you / we / they **work**.\n"
            "• He / she / it **works** (добавляем -s).\n\n"
            "Отрицание и вопросы строим с *do/does*:\n"
            "• I **don't** work on Sundays.\n"
            "• **Does** she like coffee?\n\n"
            "Маркеры: every day, usually, often, never, sometimes."
        ),
        exercises=(
            _e("He ___ English every day.", ["study", "studies", "studys", "studying"], 1, "He/she/it + -s, study → studies."),
            _e("They ___ live in Moscow.", ["don't", "doesn't", "isn't", "aren't"], 0, "They → don't."),
            _e("___ she speak French?", ["Do", "Does", "Is", "Are"], 1, "3-е л. ед. ч. → Does."),
            _e("I never ___ late.", ["is", "are", "am", "be"], 2, "I + am; never ставится перед смысловым глаголом или после be."),
        ),
    ),
    GrammarLesson(
        id="A1:articles",
        level="A1",
        title="Артикли a / an / the",
        summary="Когда ставим a, когда an, а когда the.",
        theory=(
            "• **a** — перед словом, начинающимся с согласного звука: *a cat*.\n"
            "• **an** — перед гласным звуком: *an apple*, *an hour*.\n"
            "• **the** — про конкретный предмет, уже известный собеседнику: *the sun*, *the book on the table*.\n\n"
            "Нет артикля перед именами, городами, большинством стран и перед неисчисляемыми в общем смысле: *I like music*."
        ),
        exercises=(
            _e("I saw ___ elephant at the zoo.", ["a", "an", "the", "—"], 1, "elephant начинается с гласного звука → an."),
            _e("Can you close ___ door, please?", ["a", "an", "the", "—"], 2, "Конкретная, известная дверь → the."),
            _e("She is ___ engineer.", ["a", "an", "the", "—"], 1, "engineer — гласный звук."),
            _e("___ honesty is important.", ["A", "An", "The", "—"], 3, "Абстрактное понятие в общем смысле — без артикля."),
        ),
    ),

    # ───────────── A2 ─────────────
    GrammarLesson(
        id="A2:past-simple",
        level="A2",
        title="Past Simple",
        summary="Говорим о законченных событиях в прошлом.",
        theory=(
            "Правильные глаголы: прибавляем -ed → *worked*, *played*.\n"
            "Неправильные нужно запомнить: go → **went**, see → **saw**, have → **had**.\n\n"
            "Отрицание и вопрос — через *did* + инфинитив:\n"
            "• I **didn't go** to school.\n"
            "• **Did** you see the film?\n\n"
            "Маркеры: yesterday, last week, in 2010, two days ago."
        ),
        exercises=(
            _e("We ___ to Italy last summer.", ["go", "goes", "went", "gone"], 2, "go → went в Past Simple."),
            _e("She ___ the book yesterday.", ["readed", "read", "reads", "reading"], 1, "read (читал) — неправильный, форма не меняется в написании."),
            _e("___ you call him last night?", ["Do", "Did", "Are", "Were"], 1, "Past Simple, вопрос → Did."),
            _e("They ___ come to the party.", ["don't", "didn't", "aren't", "weren't"], 1, "Отрицание в Past Simple → didn't."),
        ),
    ),
    GrammarLesson(
        id="A2:can-must",
        level="A2",
        title="Модальные: can, must, should",
        summary="Умения, разрешения, обязанности и советы.",
        theory=(
            "• **can** — умение или возможность: *I can swim*.\n"
            "• **must** — сильная обязанность или уверенность: *You must stop*.\n"
            "• **should** — совет: *You should rest*.\n\n"
            "После модальных глаголов идёт инфинитив без *to*."
        ),
        exercises=(
            _e("She ___ speak three languages.", ["cans", "can", "can to", "do can"], 1, "Модальные не склоняются и идут без to."),
            _e("You ___ wear a seatbelt — it's the law.", ["can", "should", "must", "may"], 2, "Это обязанность → must."),
            _e("If you're tired, you ___ go to bed early.", ["must", "should", "can't", "mustn't"], 1, "Совет → should."),
            _e("I'm sorry, I ___ help you right now.", ["can", "can't", "must", "should"], 1, "Отсутствие возможности → can't."),
        ),
    ),
    GrammarLesson(
        id="A2:comparatives",
        level="A2",
        title="Сравнительная и превосходная степень",
        summary="bigger, the biggest: как правильно сравнивать.",
        theory=(
            "Короткие прилагательные: +er / +est → *fast → faster → the fastest*.\n"
            "Длинные (2+ слога): more / the most → *beautiful → more beautiful → the most beautiful*.\n\n"
            "Особые: good → better → the best, bad → worse → the worst."
        ),
        exercises=(
            _e("This book is ___ than that one.", ["interesting", "more interesting", "most interesting", "interestinger"], 1, "Длинное прилагательное → more."),
            _e("He is the ___ player on the team.", ["good", "better", "best", "goodest"], 2, "good → best."),
            _e("Today is ___ than yesterday.", ["cold", "colder", "more cold", "coldest"], 1, "Короткое → +er."),
            _e("It was the ___ day of my life.", ["bad", "worse", "worst", "baddest"], 2, "bad → the worst."),
        ),
    ),

    # ───────────── B1 ─────────────
    GrammarLesson(
        id="B1:present-perfect",
        level="B1",
        title="Present Perfect",
        summary="Связь прошлого с настоящим: опыт, результат, изменения.",
        theory=(
            "Форма: **have / has + V3** (третья форма глагола).\n\n"
            "Используем когда:\n"
            "• Есть опыт: *I have been to Japan.*\n"
            "• Действие только что закончилось: *She has just arrived.*\n"
            "• Действие началось в прошлом и продолжается: *We have lived here for 5 years.*\n\n"
            "Маркеры: ever, never, already, yet, just, for, since.\n\n"
            "НЕ используем с конкретным временем в прошлом (yesterday, in 2010) — там Past Simple."
        ),
        exercises=(
            _e("I ___ never ___ such a beautiful place.", ["have / seen", "has / seen", "did / see", "have / saw"], 0, "I + have + seen (V3 от see)."),
            _e("She ___ just ___ the report.", ["have / finished", "has / finished", "is / finishing", "did / finish"], 1, "She → has; just — маркер Present Perfect."),
            _e("We ___ in London since 2018.", ["live", "lived", "have lived", "are living"], 2, "since → Present Perfect."),
            _e("___ you ever ___ sushi?", ["Did / try", "Have / tried", "Do / try", "Are / trying"], 1, "ever → Present Perfect."),
        ),
    ),
    GrammarLesson(
        id="B1:future-forms",
        level="B1",
        title="Future Simple и be going to",
        summary="Выбор между will и be going to для будущего.",
        theory=(
            "**will** — спонтанное решение, обещание, предсказание без особых оснований:\n"
            "• OK, I **will** help you.\n"
            "• I think it **will** rain tomorrow.\n\n"
            "**be going to** — план, уже принятое решение, предсказание на основании фактов:\n"
            "• We **are going to** move next month.\n"
            "• Look at those clouds! It **is going to** rain.\n\n"
            "Present Continuous тоже может выражать запланированное действие: *I'm meeting John at 6*."
        ),
        exercises=(
            _e("Look at the sky! It ___ rain.", ["will", "is going to", "rains", "is raining"], 1, "Факты (тучи) → be going to."),
            _e("— The phone is ringing. — I ___ answer it.", ["am going to", "will", "answer", "am answering"], 1, "Спонтанное решение → will."),
            _e("Next summer we ___ visit Spain — tickets are booked.", ["will", "are going to", "visit", "visited"], 1, "План с билетами → be going to."),
            _e("I promise I ___ call you back.", ["am going to", "will", "call", "am calling"], 1, "Обещание → will."),
        ),
    ),
    GrammarLesson(
        id="B1:conditional-1",
        level="B1",
        title="Условные предложения 1 типа",
        summary="Реальное условие в будущем: if + Present, will + V.",
        theory=(
            "Формула: **If + Present Simple, ... will + V**.\n\n"
            "Используем для реальных условий в будущем:\n"
            "• If it **rains**, we **will stay** home.\n"
            "• If you **study**, you **will pass**.\n\n"
            "Порядок частей не важен; если *if*-часть идёт второй, запятая не нужна:\n"
            "• We will stay home **if** it rains."
        ),
        exercises=(
            _e("If you ___ early, we'll catch the train.", ["leave", "will leave", "left", "are leaving"], 0, "В if-части — Present."),
            _e("If she studies hard, she ___ the exam.", ["pass", "passes", "will pass", "would pass"], 2, "Главная часть → will + V."),
            _e("I'll be angry if he ___ late again.", ["will be", "is", "would be", "was"], 1, "После if — Present Simple."),
            _e("If we don't hurry, we ___ the film.", ["miss", "will miss", "missed", "would miss"], 1, "Главная часть → will miss."),
        ),
    ),

    # ───────────── B2 ─────────────
    GrammarLesson(
        id="B2:passive",
        level="B2",
        title="Пассивный залог (Passive Voice)",
        summary="Когда важно действие, а не тот, кто его совершает.",
        theory=(
            "Формула: **be + V3 (причастие прошедшего времени)**.\n\n"
            "• Present Simple: *The letter is written.*\n"
            "• Past Simple: *The letter was written.*\n"
            "• Present Perfect: *The letter has been written.*\n"
            "• Future: *The letter will be written.*\n\n"
            "Исполнителя добавляем через *by*: *The book was written **by** Orwell*."
        ),
        exercises=(
            _e("The window ___ yesterday.", ["broke", "was broken", "is broken", "has broken"], 1, "yesterday → Past Simple Passive → was broken."),
            _e("A new hospital ___ next year.", ["will build", "will be built", "is built", "was built"], 1, "Future Passive → will be + V3."),
            _e("This song ___ by millions of people.", ["listens", "is listened", "is listened to", "listen"], 2, "listen to → is listened to by."),
            _e("The report ___ already.", ["has finished", "has been finished", "is finish", "finished"], 1, "Present Perfect Passive → has been finished."),
        ),
    ),
    GrammarLesson(
        id="B2:conditional-2-3",
        level="B2",
        title="Условные 2 и 3 типа",
        summary="Гипотетическое настоящее и нереальное прошлое.",
        theory=(
            "**Тип 2** — нереальное настоящее/будущее: *If + Past Simple, would + V*.\n"
            "• If I **had** more time, I **would travel** more.\n\n"
            "**Тип 3** — нереальное прошлое (сожаление): *If + Past Perfect, would have + V3*.\n"
            "• If I **had studied**, I **would have passed** the exam.\n\n"
            "В 2 типе часто используют *were* вместо was: *If I **were** you…*"
        ),
        exercises=(
            _e("If I ___ you, I would take the job.", ["am", "was", "were", "had been"], 2, "Стандарт: If I were you."),
            _e("If she had called, I ___ her.", ["would help", "would have helped", "will help", "helped"], 1, "Тип 3 → would have + V3."),
            _e("I would buy that car if I ___ rich.", ["am", "was", "were", "would be"], 2, "Тип 2, формально — were."),
            _e("If you hadn't reminded me, I ___ the meeting.", ["missed", "would miss", "would have missed", "will miss"], 2, "Тип 3 → would have missed."),
        ),
    ),
    GrammarLesson(
        id="B2:reported-speech",
        level="B2",
        title="Косвенная речь (Reported Speech)",
        summary="Как пересказать чужие слова.",
        theory=(
            "При пересказе времена сдвигаются на шаг назад:\n"
            "• Present Simple → Past Simple\n"
            "• Present Continuous → Past Continuous\n"
            "• Past Simple → Past Perfect\n"
            "• will → would\n\n"
            "Меняются и местоимения, и слова-маркеры: *today → that day*, *tomorrow → the next day*.\n\n"
            "Пример: *He said, \"I am tired.\"* → *He said (that) he **was** tired.*"
        ),
        exercises=(
            _e('She said, "I work here." → She said she ___ there.', ["work", "works", "worked", "had worked"], 2, "Present Simple → Past Simple; here → there."),
            _e('Tom said, "I will call you." → Tom said he ___ me.', ["will call", "would call", "called", "had called"], 1, "will → would."),
            _e('"I saw him yesterday," Kate said. → Kate said she ___ him the day before.', ["saw", "has seen", "had seen", "would see"], 2, "Past Simple → Past Perfect."),
            _e('"I am reading," he said. → He said he ___.', ["is reading", "was reading", "had read", "reads"], 1, "Present Continuous → Past Continuous."),
        ),
    ),

    # ───────────── C1 ─────────────
    GrammarLesson(
        id="C1:inversion",
        level="C1",
        title="Инверсия с отрицательными наречиями",
        summary="Эмфатические конструкции: Never have I seen…",
        theory=(
            "После отрицательных/ограничительных наречий в начале предложения идёт обратный порядок слов (как в вопросе):\n\n"
            "• **Never** have I seen such a thing.\n"
            "• **Hardly** had I arrived when the phone rang.\n"
            "• **Not only** does she sing, but she also plays the guitar.\n"
            "• **Only after** the meeting did we understand the plan."
        ),
        exercises=(
            _e("___ had I opened the door when the cat ran out.", ["No sooner", "Hardly", "Scarcely", "All correct"], 3, "No sooner/Hardly/Scarcely — все работают в схожем значении."),
            _e("Never ___ such a beautiful sunset.", ["I have seen", "have I seen", "I did see", "I saw"], 1, "После never — инверсия: have I seen."),
            _e("Not only ___ late, but he also forgot the gift.", ["he was", "was he", "he has been", "is he"], 1, "Инверсия: was he."),
            _e("Only then ___ I realize my mistake.", ["did", "do", "have", "was"], 0, "После only then — do-support: did I realize."),
        ),
    ),
    GrammarLesson(
        id="C1:subjunctive-advanced",
        level="C1",
        title="Wish / If only и смешанные условные",
        summary="Тонкие оттенки сожаления и желания.",
        theory=(
            "• *I wish / If only* + **Past Simple** — сожаление о настоящем:\n"
            "  *I wish I **knew** the answer.*\n"
            "• + **Past Perfect** — сожаление о прошлом:\n"
            "  *I wish I **had told** her the truth.*\n"
            "• + **would** — раздражение/просьба об изменении поведения:\n"
            "  *I wish you **wouldn't** shout.*\n\n"
            "Смешанные условные: *If I had studied medicine (прошлое), I would be a doctor now (настоящее).*"
        ),
        exercises=(
            _e("I wish I ___ taller.", ["am", "was", "were", "had been"], 2, "Сожаление о настоящем → were."),
            _e("If only we ___ the bus ten minutes ago!", ["didn't miss", "hadn't missed", "wouldn't miss", "weren't missing"], 1, "Прошлое → Past Perfect."),
            _e("I wish you ___ me when you're eating.", ["don't call", "wouldn't call", "hadn't called", "didn't call"], 1, "Раздражение на повторяющееся поведение → wouldn't."),
            _e("If I hadn't quit that job, I ___ much more money now.", ["would earn", "would have earned", "earned", "will earn"], 0, "Смешанное: прошлое → настоящее, would + V."),
        ),
    ),
]


BY_ID: dict[str, GrammarLesson] = {l.id: l for l in LESSONS}
BY_LEVEL: dict[str, list[GrammarLesson]] = {}
for l in LESSONS:
    BY_LEVEL.setdefault(l.level, []).append(l)


def lessons_for_level(level: str) -> list[GrammarLesson]:
    return BY_LEVEL.get(level, [])


def get_lesson(lesson_id: str) -> GrammarLesson | None:
    return BY_ID.get(lesson_id)
