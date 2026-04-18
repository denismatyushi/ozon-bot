"""Curated vocabulary lists per CEFR level.

Word ids are stable ("A1:hello") so the database can track progress reliably.
"""
from src.models.content import Word


def _w(level: str, en: str, ru: str, transcription: str, example_en: str,
       example_ru: str, topic: str) -> Word:
    return Word(
        id=f"{level}:{en.lower().replace(' ', '_')}",
        level=level, en=en, ru=ru, transcription=transcription,
        example_en=example_en, example_ru=example_ru, topic=topic,
    )


A1 = [
    # Greetings & basics
    _w("A1", "hello", "привет", "[həˈloʊ]", "Hello, my name is Anna.", "Привет, меня зовут Анна.", "greetings"),
    _w("A1", "goodbye", "до свидания", "[ɡʊdˈbaɪ]", "Goodbye, see you tomorrow.", "До свидания, увидимся завтра.", "greetings"),
    _w("A1", "please", "пожалуйста", "[pliːz]", "Pass me the salt, please.", "Передай мне соль, пожалуйста.", "greetings"),
    _w("A1", "thank you", "спасибо", "[ˈθæŋk juː]", "Thank you for the gift.", "Спасибо за подарок.", "greetings"),
    _w("A1", "yes", "да", "[jes]", "Yes, I agree.", "Да, я согласен.", "basics"),
    _w("A1", "no", "нет", "[noʊ]", "No, I don't want tea.", "Нет, я не хочу чай.", "basics"),
    _w("A1", "sorry", "извини", "[ˈsɒri]", "Sorry, I'm late.", "Извини, я опоздал.", "greetings"),
    # Family
    _w("A1", "mother", "мама", "[ˈmʌðər]", "My mother is a doctor.", "Моя мама — врач.", "family"),
    _w("A1", "father", "папа", "[ˈfɑːðər]", "My father works in a bank.", "Мой папа работает в банке.", "family"),
    _w("A1", "brother", "брат", "[ˈbrʌðər]", "I have one brother.", "У меня есть один брат.", "family"),
    _w("A1", "sister", "сестра", "[ˈsɪstər]", "My sister is ten years old.", "Моей сестре десять лет.", "family"),
    _w("A1", "friend", "друг", "[frend]", "She is my best friend.", "Она мой лучший друг.", "family"),
    # Colors
    _w("A1", "red", "красный", "[red]", "The apple is red.", "Яблоко красное.", "colors"),
    _w("A1", "blue", "синий", "[bluː]", "The sky is blue.", "Небо синее.", "colors"),
    _w("A1", "green", "зелёный", "[ɡriːn]", "Grass is green.", "Трава зелёная.", "colors"),
    _w("A1", "white", "белый", "[waɪt]", "Snow is white.", "Снег белый.", "colors"),
    _w("A1", "black", "чёрный", "[blæk]", "I have black hair.", "У меня чёрные волосы.", "colors"),
    # Food
    _w("A1", "water", "вода", "[ˈwɔːtər]", "I drink water every day.", "Я пью воду каждый день.", "food"),
    _w("A1", "bread", "хлеб", "[bred]", "We bought fresh bread.", "Мы купили свежий хлеб.", "food"),
    _w("A1", "apple", "яблоко", "[ˈæpl]", "An apple a day keeps the doctor away.", "Яблоко в день избавляет от необходимости врача.", "food"),
    _w("A1", "milk", "молоко", "[mɪlk]", "Children drink milk.", "Дети пьют молоко.", "food"),
    # Common verbs
    _w("A1", "be", "быть", "[biː]", "I am a student.", "Я студент.", "verbs"),
    _w("A1", "have", "иметь", "[hæv]", "I have a car.", "У меня есть машина.", "verbs"),
    _w("A1", "go", "идти, ехать", "[ɡoʊ]", "I go to school.", "Я иду в школу.", "verbs"),
    _w("A1", "eat", "есть", "[iːt]", "We eat dinner at seven.", "Мы ужинаем в семь.", "verbs"),
    _w("A1", "drink", "пить", "[drɪŋk]", "I drink coffee in the morning.", "Я пью кофе утром.", "verbs"),
    _w("A1", "read", "читать", "[riːd]", "She reads books every evening.", "Она читает книги каждый вечер.", "verbs"),
    _w("A1", "write", "писать", "[raɪt]", "He writes letters to his grandma.", "Он пишет письма бабушке.", "verbs"),
    _w("A1", "see", "видеть", "[siː]", "I see a bird.", "Я вижу птицу.", "verbs"),
    _w("A1", "love", "любить", "[lʌv]", "I love my family.", "Я люблю свою семью.", "verbs"),
    # Numbers / time
    _w("A1", "one", "один", "[wʌn]", "One plus one is two.", "Один плюс один — два.", "numbers"),
    _w("A1", "today", "сегодня", "[təˈdeɪ]", "Today is Monday.", "Сегодня понедельник.", "time"),
    _w("A1", "tomorrow", "завтра", "[təˈmɒroʊ]", "See you tomorrow.", "Увидимся завтра.", "time"),
    _w("A1", "house", "дом", "[haʊs]", "My house is small.", "Мой дом маленький.", "places"),
    _w("A1", "book", "книга", "[bʊk]", "This book is interesting.", "Эта книга интересная.", "objects"),
]

A2 = [
    _w("A2", "breakfast", "завтрак", "[ˈbrekfəst]", "I usually have breakfast at 8.", "Я обычно завтракаю в 8.", "food"),
    _w("A2", "dinner", "ужин", "[ˈdɪnər]", "Dinner is ready!", "Ужин готов!", "food"),
    _w("A2", "job", "работа", "[dʒɒb]", "She has a good job.", "У неё хорошая работа.", "work"),
    _w("A2", "money", "деньги", "[ˈmʌni]", "I don't have much money.", "У меня мало денег.", "work"),
    _w("A2", "busy", "занятый", "[ˈbɪzi]", "I'm busy right now.", "Сейчас я занят.", "describing"),
    _w("A2", "tired", "уставший", "[ˈtaɪərd]", "I'm too tired to cook.", "Я слишком устал, чтобы готовить.", "describing"),
    _w("A2", "happy", "счастливый", "[ˈhæpi]", "She looks happy today.", "Сегодня она выглядит счастливой.", "describing"),
    _w("A2", "angry", "злой", "[ˈæŋɡri]", "Don't be angry with me.", "Не злись на меня.", "describing"),
    _w("A2", "buy", "покупать", "[baɪ]", "I want to buy a new phone.", "Я хочу купить новый телефон.", "verbs"),
    _w("A2", "sell", "продавать", "[sel]", "They sell fresh vegetables.", "Они продают свежие овощи.", "verbs"),
    _w("A2", "travel", "путешествовать", "[ˈtrævəl]", "We travel every summer.", "Мы путешествуем каждое лето.", "verbs"),
    _w("A2", "hotel", "отель", "[hoʊˈtel]", "The hotel was very nice.", "Отель был очень хороший.", "travel"),
    _w("A2", "airport", "аэропорт", "[ˈerpɔːrt]", "The airport is far from here.", "Аэропорт далеко отсюда.", "travel"),
    _w("A2", "ticket", "билет", "[ˈtɪkɪt]", "I bought two tickets.", "Я купил два билета.", "travel"),
    _w("A2", "city", "город", "[ˈsɪti]", "London is a big city.", "Лондон — большой город.", "places"),
    _w("A2", "country", "страна", "[ˈkʌntri]", "Japan is a beautiful country.", "Япония — красивая страна.", "places"),
    _w("A2", "weather", "погода", "[ˈweðər]", "The weather is great today.", "Сегодня отличная погода.", "nature"),
    _w("A2", "rain", "дождь", "[reɪn]", "I love the sound of rain.", "Я люблю звук дождя.", "nature"),
    _w("A2", "cold", "холодный", "[koʊld]", "It's cold outside.", "На улице холодно.", "nature"),
    _w("A2", "hot", "жаркий", "[hɒt]", "It's really hot today.", "Сегодня действительно жарко.", "nature"),
    _w("A2", "quickly", "быстро", "[ˈkwɪkli]", "She speaks too quickly.", "Она говорит слишком быстро.", "adverbs"),
    _w("A2", "slowly", "медленно", "[ˈsloʊli]", "Please speak more slowly.", "Пожалуйста, говорите медленнее.", "adverbs"),
    _w("A2", "remember", "помнить", "[rɪˈmembər]", "I don't remember his name.", "Я не помню его имя.", "verbs"),
    _w("A2", "forget", "забывать", "[fərˈɡet]", "Don't forget to call me.", "Не забудь позвонить мне.", "verbs"),
    _w("A2", "meet", "встречать", "[miːt]", "Let's meet at 6 pm.", "Давай встретимся в 18:00.", "verbs"),
    _w("A2", "language", "язык", "[ˈlæŋɡwɪdʒ]", "English is a global language.", "Английский — мировой язык.", "education"),
    _w("A2", "learn", "учить(ся)", "[lɜːrn]", "I learn English every day.", "Я учу английский каждый день.", "education"),
    _w("A2", "homework", "домашнее задание", "[ˈhoʊmwɜːrk]", "Did you do your homework?", "Ты сделал домашнее задание?", "education"),
    _w("A2", "answer", "ответ", "[ˈænsər]", "Your answer is correct.", "Твой ответ правильный.", "education"),
    _w("A2", "question", "вопрос", "[ˈkwestʃən]", "Can I ask a question?", "Можно задать вопрос?", "education"),
]

B1 = [
    _w("B1", "experience", "опыт", "[ɪkˈspɪəriəns]", "She has five years of experience.", "У неё пять лет опыта.", "work"),
    _w("B1", "achieve", "достигать", "[əˈtʃiːv]", "He achieved his goal.", "Он достиг своей цели.", "verbs"),
    _w("B1", "decide", "решать", "[dɪˈsaɪd]", "I decided to quit smoking.", "Я решил бросить курить.", "verbs"),
    _w("B1", "suggest", "предлагать", "[səˈdʒest]", "I suggest going by train.", "Я предлагаю поехать поездом.", "verbs"),
    _w("B1", "avoid", "избегать", "[əˈvɔɪd]", "Avoid junk food.", "Избегай вредной еды.", "verbs"),
    _w("B1", "improve", "улучшать", "[ɪmˈpruːv]", "I want to improve my English.", "Я хочу улучшить свой английский.", "verbs"),
    _w("B1", "receive", "получать", "[rɪˈsiːv]", "I received a letter yesterday.", "Я получил письмо вчера.", "verbs"),
    _w("B1", "provide", "предоставлять", "[prəˈvaɪd]", "We provide free delivery.", "Мы предоставляем бесплатную доставку.", "verbs"),
    _w("B1", "opportunity", "возможность", "[ˌɒpərˈtjuːnəti]", "Don't miss this opportunity.", "Не упускай эту возможность.", "abstract"),
    _w("B1", "environment", "окружение, среда", "[ɪnˈvaɪrənmənt]", "We must protect the environment.", "Мы должны защищать окружающую среду.", "nature"),
    _w("B1", "government", "правительство", "[ˈɡʌvərnmənt]", "The government passed a new law.", "Правительство приняло новый закон.", "society"),
    _w("B1", "society", "общество", "[səˈsaɪəti]", "Technology shapes society.", "Технологии формируют общество.", "society"),
    _w("B1", "culture", "культура", "[ˈkʌltʃər]", "I'm interested in Japanese culture.", "Я интересуюсь японской культурой.", "society"),
    _w("B1", "research", "исследование", "[rɪˈsɜːrtʃ]", "The research shows interesting results.", "Исследование показывает интересные результаты.", "education"),
    _w("B1", "article", "статья", "[ˈɑːrtɪkl]", "I read an article about space.", "Я читал статью про космос.", "education"),
    _w("B1", "advice", "совет", "[ədˈvaɪs]", "Thanks for your advice.", "Спасибо за совет.", "abstract"),
    _w("B1", "consider", "рассматривать", "[kənˈsɪdər]", "Consider all the options.", "Рассмотри все варианты.", "verbs"),
    _w("B1", "depend", "зависеть", "[dɪˈpend]", "It depends on the weather.", "Это зависит от погоды.", "verbs"),
    _w("B1", "notice", "замечать", "[ˈnoʊtɪs]", "I didn't notice the change.", "Я не заметил изменения.", "verbs"),
    _w("B1", "recognize", "узнавать", "[ˈrekəɡnaɪz]", "I didn't recognize him at first.", "Я не сразу его узнал.", "verbs"),
    _w("B1", "although", "хотя", "[ɔːlˈðoʊ]", "Although it was cold, we walked.", "Хотя было холодно, мы гуляли.", "connectors"),
    _w("B1", "therefore", "поэтому", "[ˈðerfɔːr]", "He was late; therefore, he apologized.", "Он опоздал, поэтому извинился.", "connectors"),
    _w("B1", "however", "однако", "[haʊˈevər]", "It rained; however, we went out.", "Шёл дождь, однако мы вышли.", "connectors"),
    _w("B1", "according to", "согласно", "[əˈkɔːrdɪŋ tuː]", "According to the report, sales are up.", "Согласно отчёту, продажи выросли.", "connectors"),
    _w("B1", "pollution", "загрязнение", "[pəˈluːʃn]", "Air pollution is a serious problem.", "Загрязнение воздуха — серьёзная проблема.", "nature"),
    _w("B1", "develop", "развивать", "[dɪˈveləp]", "Children develop quickly.", "Дети быстро развиваются.", "verbs"),
]

B2 = [
    _w("B2", "achievement", "достижение", "[əˈtʃiːvmənt]", "Winning the award was a great achievement.", "Победа в конкурсе — большое достижение.", "abstract"),
    _w("B2", "maintain", "поддерживать", "[meɪnˈteɪn]", "It's important to maintain a healthy lifestyle.", "Важно поддерживать здоровый образ жизни.", "verbs"),
    _w("B2", "establish", "устанавливать, основывать", "[ɪˈstæblɪʃ]", "The company was established in 1990.", "Компания была основана в 1990.", "verbs"),
    _w("B2", "implement", "внедрять", "[ˈɪmplɪment]", "We implemented new policies.", "Мы внедрили новые правила.", "verbs"),
    _w("B2", "assume", "предполагать", "[əˈsjuːm]", "I assume you've met before.", "Полагаю, вы уже встречались.", "verbs"),
    _w("B2", "demonstrate", "демонстрировать", "[ˈdemənstreɪt]", "Let me demonstrate how it works.", "Позвольте показать, как это работает.", "verbs"),
    _w("B2", "contradict", "противоречить", "[ˌkɒntrəˈdɪkt]", "Her words contradict her actions.", "Её слова противоречат действиям.", "verbs"),
    _w("B2", "reliable", "надёжный", "[rɪˈlaɪəbl]", "He is a reliable employee.", "Он надёжный сотрудник.", "describing"),
    _w("B2", "inevitable", "неизбежный", "[ɪnˈevɪtəbl]", "Change is inevitable.", "Перемены неизбежны.", "describing"),
    _w("B2", "significant", "значительный", "[sɪɡˈnɪfɪkənt]", "There was a significant improvement.", "Произошло значительное улучшение.", "describing"),
    _w("B2", "controversial", "спорный", "[ˌkɒntrəˈvɜːrʃl]", "It's a controversial topic.", "Это спорная тема.", "describing"),
    _w("B2", "assumption", "предположение", "[əˈsʌmpʃn]", "Your assumption is wrong.", "Твоё предположение неверно.", "abstract"),
    _w("B2", "consequence", "последствие", "[ˈkɒnsɪkwəns]", "Actions have consequences.", "У действий есть последствия.", "abstract"),
    _w("B2", "approach", "подход", "[əˈproʊtʃ]", "We need a new approach.", "Нам нужен новый подход.", "abstract"),
    _w("B2", "perspective", "точка зрения", "[pərˈspektɪv]", "From my perspective, it's fine.", "С моей точки зрения, это нормально.", "abstract"),
    _w("B2", "regardless", "независимо", "[rɪˈɡɑːrdləs]", "We'll go regardless of the weather.", "Мы пойдём независимо от погоды.", "connectors"),
    _w("B2", "nevertheless", "тем не менее", "[ˌnevərðəˈles]", "It was tough; nevertheless, we won.", "Было тяжело, тем не менее мы победили.", "connectors"),
    _w("B2", "whereas", "тогда как", "[werˈæz]", "He likes tea, whereas she likes coffee.", "Он любит чай, тогда как она любит кофе.", "connectors"),
    _w("B2", "emphasize", "подчёркивать", "[ˈemfəsaɪz]", "She emphasized the need for action.", "Она подчеркнула необходимость действий.", "verbs"),
    _w("B2", "overwhelm", "подавлять, захлёстывать", "[ˌoʊvərˈwelm]", "I feel overwhelmed by work.", "Меня захлёстывает работа.", "verbs"),
    _w("B2", "deadline", "крайний срок", "[ˈdedlaɪn]", "The deadline is Friday.", "Дедлайн — пятница.", "work"),
    _w("B2", "negotiate", "вести переговоры", "[nɪˈɡoʊʃieɪt]", "We need to negotiate the price.", "Нам нужно обсудить цену.", "work"),
]

C1 = [
    _w("C1", "meticulous", "дотошный, скрупулёзный", "[məˈtɪkjələs]", "She is meticulous about details.", "Она скрупулёзна в деталях.", "describing"),
    _w("C1", "ubiquitous", "вездесущий", "[juːˈbɪkwɪtəs]", "Smartphones have become ubiquitous.", "Смартфоны стали повсеместными.", "describing"),
    _w("C1", "nuance", "нюанс", "[ˈnjuːɑːns]", "The nuance of the argument matters.", "Нюанс аргумента имеет значение.", "abstract"),
    _w("C1", "substantiate", "подтверждать", "[səbˈstænʃieɪt]", "Can you substantiate this claim?", "Можете подтвердить это утверждение?", "verbs"),
    _w("C1", "discern", "различать", "[dɪˈsɜːrn]", "It's hard to discern the truth.", "Трудно распознать правду.", "verbs"),
    _w("C1", "mitigate", "смягчать", "[ˈmɪtɪɡeɪt]", "Measures to mitigate the risk were taken.", "Были приняты меры для снижения риска.", "verbs"),
    _w("C1", "cogent", "убедительный", "[ˈkoʊdʒənt]", "He made a cogent argument.", "Он привёл убедительный аргумент.", "describing"),
    _w("C1", "tentative", "предварительный", "[ˈtentətɪv]", "We have a tentative agreement.", "У нас предварительное соглашение.", "describing"),
    _w("C1", "pertinent", "уместный", "[ˈpɜːrtɪnənt]", "Please stick to pertinent facts.", "Пожалуйста, придерживайтесь уместных фактов.", "describing"),
    _w("C1", "resilient", "стойкий, гибкий", "[rɪˈzɪliənt]", "Children are remarkably resilient.", "Дети удивительно стойкие.", "describing"),
    _w("C1", "scrutiny", "пристальное внимание", "[ˈskruːtəni]", "The plan was under close scrutiny.", "План находился под пристальным вниманием.", "abstract"),
    _w("C1", "paradigm", "парадигма", "[ˈpærədaɪm]", "It's a paradigm shift in science.", "Это смена парадигмы в науке.", "abstract"),
    _w("C1", "endeavour", "стремиться", "[ɪnˈdevər]", "We endeavour to improve every year.", "Мы стремимся становиться лучше каждый год.", "verbs"),
    _w("C1", "concede", "уступать, признавать", "[kənˈsiːd]", "He conceded that he was wrong.", "Он признал, что был неправ.", "verbs"),
    _w("C1", "elaborate", "подробно описывать", "[ɪˈlæbəreɪt]", "Could you elaborate on that?", "Могли бы вы пояснить подробнее?", "verbs"),
    _w("C1", "compelling", "убедительный, захватывающий", "[kəmˈpelɪŋ]", "It's a compelling story.", "Это захватывающая история.", "describing"),
    _w("C1", "fluctuate", "колебаться", "[ˈflʌktʃueɪt]", "Prices fluctuate with the season.", "Цены колеблются в зависимости от сезона.", "verbs"),
    _w("C1", "scarcity", "дефицит", "[ˈskersəti]", "Water scarcity is a global issue.", "Дефицит воды — глобальная проблема.", "abstract"),
    _w("C1", "counterpart", "аналог, коллега", "[ˈkaʊntərpɑːrt]", "She met with her French counterpart.", "Она встретилась со своим французским коллегой.", "abstract"),
    _w("C1", "leverage", "использовать эффективно", "[ˈlevərɪdʒ]", "They leveraged social media to grow.", "Они использовали соцсети для роста.", "verbs"),
]


ALL_WORDS: list[Word] = A1 + A2 + B1 + B2 + C1
BY_ID: dict[str, Word] = {w.id: w for w in ALL_WORDS}
BY_LEVEL: dict[str, list[Word]] = {"A1": A1, "A2": A2, "B1": B1, "B2": B2, "C1": C1}


def words_for_level(level: str) -> list[Word]:
    return BY_LEVEL.get(level, [])


def get_word(word_id: str) -> Word | None:
    return BY_ID.get(word_id)
