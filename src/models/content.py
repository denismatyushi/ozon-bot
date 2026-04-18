from dataclasses import dataclass, field


@dataclass(frozen=True)
class Word:
    """A vocabulary entry tied to a CEFR level."""
    id: str                   # stable id, e.g. "A1:hello"
    level: str                # "A1".."C1"
    en: str
    ru: str
    transcription: str = ""
    example_en: str = ""
    example_ru: str = ""
    topic: str = ""


@dataclass(frozen=True)
class Exercise:
    prompt: str               # sentence or question, may contain ___
    options: tuple[str, ...]
    correct: int              # index in options
    explanation: str = ""


@dataclass(frozen=True)
class GrammarLesson:
    id: str                   # "A1:present-simple-be"
    level: str
    title: str
    summary: str              # 1-2 line teaser
    theory: str               # Markdown-safe explanation
    exercises: tuple[Exercise, ...]


@dataclass(frozen=True)
class PlacementQuestion:
    level: str                # which level this question probes
    prompt: str
    options: tuple[str, ...]
    correct: int
    explanation: str = ""


@dataclass(frozen=True)
class LevelInfo:
    code: str                 # "A1"
    name: str                 # "Beginner"
    description: str
