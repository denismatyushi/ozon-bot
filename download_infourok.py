"""
Скрипт для скачивания материала с infourok.ru.
Требует cookies из браузера после авторизации на сайте.

Как получить cookies:
1. Войди на https://infourok.ru в браузере
2. Открой DevTools (F12) -> Application -> Cookies -> https://infourok.ru
3. Скопируй значения нужных cookies в словарь COOKIES ниже
"""

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://infourok.ru/magazin-materialov/razgovory-o-vazhnom-65-let-triumfa-ko-dnyu-kosmonavtiki-rabochij-list-dlya-nachalnoj-shkoly-1473154"

# Вставь свои cookies после входа на сайт
COOKIES = {
    # Пример:
    # "PHPSESSID": "your_session_id_here",
    # "auth_token": "your_auth_token_here",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://infourok.ru/",
    "Accept-Language": "ru-RU,ru;q=0.9",
}


def fetch_page(session: requests.Session) -> BeautifulSoup:
    resp = session.get(URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def find_download_url(soup: BeautifulSoup) -> str | None:
    # Ищем прямую ссылку на файл
    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if re.search(r"\.(pdf|docx?|pptx?|zip)(\?|$)", href, re.IGNORECASE):
            return href

    # Ищем кнопку скачивания
    for tag in soup.find_all("a", href=True):
        text = tag.get_text(strip=True).lower()
        href = tag["href"]
        if any(w in text for w in ("скачать", "download", "получить")):
            if href.startswith("http"):
                return href

    # Ищем в data-атрибутах
    for tag in soup.find_all(attrs={"data-href": True}):
        return tag["data-href"]

    return None


def download_file(session: requests.Session, file_url: str, output_dir: Path) -> Path:
    if not file_url.startswith("http"):
        file_url = "https://infourok.ru" + file_url

    resp = session.get(file_url, headers=HEADERS, stream=True, timeout=60)
    resp.raise_for_status()

    # Определяем имя файла
    content_disp = resp.headers.get("Content-Disposition", "")
    match = re.search(r'filename[^;=\n]*=(["\']?)([^"\';\n]+)\1', content_disp)
    if match:
        filename = match.group(2).strip()
    else:
        filename = file_url.split("/")[-1].split("?")[0] or "material"

    output_path = output_dir / filename
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    return output_path


def main() -> None:
    output_dir = Path("downloads")
    output_dir.mkdir(exist_ok=True)

    session = requests.Session()
    session.cookies.update(COOKIES)

    print(f"Загружаем страницу: {URL}")
    try:
        soup = fetch_page(session)
    except requests.HTTPError as e:
        print(f"Ошибка при загрузке страницы: {e}")
        if e.response.status_code == 403:
            print("Доступ запрещён. Проверь, что cookies добавлены и ты авторизован.")
        sys.exit(1)

    print("Ищем ссылку на файл...")
    file_url = find_download_url(soup)

    if not file_url:
        print("Ссылка на файл не найдена. Страница могла измениться или требует авторизации.")
        print("\nСохраняем HTML для анализа -> page_debug.html")
        Path("page_debug.html").write_text(soup.prettify(), encoding="utf-8")
        sys.exit(1)

    print(f"Найдена ссылка: {file_url}")
    print("Скачиваем файл...")
    output_path = download_file(session, file_url, output_dir)
    print(f"Файл сохранён: {output_path}")


if __name__ == "__main__":
    main()
