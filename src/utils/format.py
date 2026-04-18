"""Small formatting helpers."""
import re

_BOLD = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", re.DOTALL)


def md_to_html(text: str) -> str:
    """Convert a tiny subset of Markdown (**bold**, *italic*) to Telegram HTML."""
    text = _BOLD.sub(r"<b>\1</b>", text)
    text = _ITALIC.sub(r"<i>\1</i>", text)
    return text
