"""
Скрипт для скачивания материала с infourok.ru.
Авторизуется по логину и паролю автоматически.

Запуск:
    python download_infourok.py
"""

import re
import sys
from getpass import getpass
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://infourok.ru/magazin-materialov/razgovory-o-vazhnom-65-let-triumfa-ko-dnyu-kosmonavtiki-rabochij-list-dlya-nachalnoj-shkoly-1473154"

LOGIN_URL = "https://infourok.ru/login"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://infourok.ru/",
    "Accept-Language": "ru-RU,ru;q=0.9",
}


def login(session: requests.Session, email: str, password: str) -> bool:
    # Получаем страницу логина для csrf-токена
    resp = session.get(LOGIN_URL, headers=HEADERS, timeout=30)
    soup = BeautifulSoup(resp.text, "html.parser")

    # Ищем csrf / hidden поля формы
    form = soup.find("form")
    payload: dict[str, str] = {}
    if form:
        for inp in form.find_all("input", {"type": ["hidden", "text", "email", "password"]}):
            name = inp.get("name")
            value = inp.get("value", "")
            if name:
                payload[name] = value

    # Подставляем credentials
    for key in list(payload.keys()):
        if "email" in key.lower() or "login" in key.lower() or "user" in key.lower():
            payload[key] = email
        if "pass" in key.lower():
            payload[key] = password

    # Если форма не нашла нужных полей — пробуем типичные имена
    payload.setdefault("email", email)
    payload.setdefault("password", password)

    action = form["action"] if form and form.get("action") else LOGIN_URL
    if not action.startswith("http"):
        action = "https://infourok.ru" + action

    headers = {**HEADERS, "Referer": LOGIN_URL, "Content-Type": "application/x-www-form-urlencoded"}
    resp = session.post(action, data=payload, headers=headers, timeout=30, allow_redirects=True)

    # Проверяем, что вошли
    if "logout" in resp.text.lower() or "выйти" in resp.text.lower():
        return True
    if resp.url and "login" not in resp.url:
        return True
    return False


def fetch_page(session: requests.Session) -> BeautifulSoup:
    resp = session.get(URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def find_download_url(soup: BeautifulSoup) -> str | None:
    # Прямая ссылка на файл по расширению
    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if re.search(r"\.(pdf|docx?|pptx?|zip)(\?|$)", href, re.IGNORECASE):
            return href

    # Кнопка скачивания по тексту
    for tag in soup.find_all("a", href=True):
        text = tag.get_text(strip=True).lower()
        href = tag["href"]
        if any(w in text for w in ("скачать", "download", "получить")):
            if href.startswith("http"):
                return href

    # data-атрибуты
    for tag in soup.find_all(attrs={"data-href": True}):
        return tag["data-href"]

    return None


def download_file(session: requests.Session, file_url: str, output_dir: Path) -> Path:
    if not file_url.startswith("http"):
        file_url = "https://infourok.ru" + file_url

    resp = session.get(file_url, headers=HEADERS, stream=True, timeout=60)
    resp.raise_for_status()

    content_disp = resp.headers.get("Content-Disposition", "")
    match = re.search(r'filename[^;=\n]*=(["\']?)([^"\';\n]+)\1', content_disp)
    filename = match.group(2).strip() if match else (file_url.split("/")[-1].split("?")[0] or "material")

    output_path = output_dir / filename
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    return output_path


def main() -> None:
    output_dir = Path("downloads")
    output_dir.mkdir(exist_ok=True)

    print("=== Скачивание материала с infourok.ru ===\n")
    email = input("Email / логин: ").strip()
    password = getpass("Пароль: ")

    session = requests.Session()

    print("\nВходим в аккаунт...")
    ok = login(session, email, password)
    if not ok:
        print("Не удалось войти. Проверь логин и пароль.")
        sys.exit(1)
    print("Авторизация успешна.")

    print(f"\nЗагружаем страницу материала...")
    try:
        soup = fetch_page(session)
    except requests.HTTPError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)

    print("Ищем ссылку на файл...")
    file_url = find_download_url(soup)

    if not file_url:
        print("Ссылка на файл не найдена (возможно, материал платный или страница изменилась).")
        print("Сохраняем HTML для анализа -> page_debug.html")
        Path("page_debug.html").write_text(soup.prettify(), encoding="utf-8")
        sys.exit(1)

    print(f"Найдена ссылка: {file_url}")
    print("Скачиваем...")
    output_path = download_file(session, file_url, output_dir)
    print(f"\nГотово! Файл сохранён: {output_path}")


if __name__ == "__main__":
    main()
