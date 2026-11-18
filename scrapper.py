import csv
import re
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
NEWS_URLS = [
    "https://tirto.id/riset-protocol-gap-indonesia-soroti-kerentanan-media-di-era-ai-hEne",
]

EMAIL = "rafainasaida@gmail.com"  

USER_AGENT = f"AcademicNewsScraper/1.0 (Tugas Etika Pengambilan Data ITS; contact: {EMAIL})"
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "id-ID,id;q=0.9"}
DELAY = 3
TIMEOUT = 15
CSV_PATH = Path(__file__).resolve().parent / "hasil_berita.csv"
def check_robots(url):
    p = urlparse(url)
    robots_url = f"{p.scheme}://{p.netloc}/robots.txt"
    try:
        r = requests.get(robots_url, headers=HEADERS, timeout=TIMEOUT)
        time.sleep(DELAY)
    except requests.RequestException as e:
        print("  robots.txt tidak bisa diakses:", e)
        return False

    if r.status_code == 404:
        print("  robots.txt tidak ada, lanjut dengan jeda dan volume kecil.")
        return True
    if r.status_code != 200:
        print(f"  robots.txt status {r.status_code}, berhenti.")
        return False

    rp = RobotFileParser()
    rp.parse(r.text.splitlines())
    allowed = rp.can_fetch(USER_AGENT, url)
    print("  robots.txt:", "diizinkan" if allowed else "DILARANG")
    return allowed

def get_page(url):
    if not check_robots(url):
        return None
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        print("  Status halaman:", r.status_code)
        r.raise_for_status()
        return r.text
    except requests.RequestException as e:
        print("  Gagal mengambil halaman:", e)
        return None
    finally:
        time.sleep(DELAY)

def meta(soup, *selectors):
    for sel in selectors:
        tag = soup.select_one(sel)
        if tag and tag.get("content"):
            return tag["content"].strip()
    return ""


def make_summary(description, content, max_chars=400):
    if description and len(description) > 60:
        text = description
    else:
        sentences = re.split(r"(?<=[.!?])\s+", content.replace("\n", " "))
        text = " ".join(sentences[:3])
    text = text.strip()
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + "..."
    return text


def parse_article(html, url):
    soup = BeautifulSoup(html, "html.parser")

    title = meta(soup, 'meta[property="og:title"]')
    if not title and soup.h1:
        title = soup.h1.get_text(" ", strip=True)
    if not title:
        return None

    description = meta(soup, 'meta[property="og:description"]', 'meta[name="description"]')

    container = soup.select_one("article") or soup
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    content = "\n".join(p for p in paragraphs if len(p) > 40)

    return {
        "judul": title,
        "ringkasan": make_summary(description, content),
        "link": url,
    }
def main():
    if "email-kamu" in EMAIL:
        print("Ganti dulu nilai EMAIL di bagian konfigurasi dengan emailmu yang aktif.")
        return

    results = []
    for url in NEWS_URLS:
        print("Memproses:", url)
        html = get_page(url)
        if html:
            item = parse_article(html, url)
            if item:
                results.append(item)

    if not results:
        print("Tidak ada data yang berhasil dikumpulkan.")
        return

    print("\n" + "=" * 50)
    for item in results:
        print("Judul     :", item["judul"])
        print("Ringkasan :", item["ringkasan"])
        print("Link      :", item["link"])
        print("-" * 50)

    with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["judul", "ringkasan", "link"])
        w.writeheader()
        w.writerows(results)
    print("Tersimpan di:", CSV_PATH)


if __name__ == "__main__":
    main()