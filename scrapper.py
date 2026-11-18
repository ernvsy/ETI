import csv
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

INDEX_URL = "https://tirto.id/"   
EXTRA_URLS = [
    "https://tirto.id/riset-protocol-gap-indonesia-soroti-kerentanan-media-di-era-ai-hEne",
]                                  
MAX_ARTICLES = 20              

EMAIL = "rafainasaida@gmail.com"
USER_AGENT = f"AcademicNewsScraper/1.0 (Tugas Etika Pengambilan Data ITS; contact: {EMAIL})"
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "id-ID,id;q=0.9"}
DELAY = 3
TIMEOUT = 15
CSV_PATH = Path(__file__).resolve().parent / "hasil_berita.csv"

_robots_cache = {}


# ---------- robots.txt checker (di-cache per domain) ----------
def check_robots(url):
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"

    if base not in _robots_cache:
        try:
            r = requests.get(f"{base}/robots.txt", headers=HEADERS, timeout=TIMEOUT)
            time.sleep(DELAY)
        except requests.RequestException as e:
            print("  robots.txt tidak bisa diakses:", e)
            _robots_cache[base] = None
            return False

        if r.status_code == 404:
            print("  robots.txt tidak ada, lanjut dengan jeda dan volume kecil.")
            _robots_cache[base] = "ALLOW"
        elif r.status_code != 200:
            print(f"  robots.txt status {r.status_code}, berhenti.")
            _robots_cache[base] = None
        else:
            rp = RobotFileParser()
            rp.parse(r.text.splitlines())
            _robots_cache[base] = rp

    rp = _robots_cache[base]
    if rp is None:
        return False
    if rp == "ALLOW":
        return True
    return rp.can_fetch(USER_AGENT, url)


# ---------- Ambil halaman ----------
def get_page(url):
    if not check_robots(url):
        print("  Dilewati (robots.txt): ", url)
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


# ---------- Cari link artikel dari halaman indeks ----------
def collect_links(index_url, limit):
    print("Mengambil daftar artikel dari:", index_url)
    html = get_page(index_url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    domain = urlparse(index_url).netloc

    links = []
    for a in soup.find_all("a", href=True):
        full = urljoin(index_url, a["href"]).split("#")[0].split("?")[0]
        p = urlparse(full)
        # ciri link artikel: domain sama, 1 segmen path, slug panjang berhubung tanda "-"
        if p.netloc == domain and p.path.count("/") == 1 and p.path.count("-") >= 3:
            if full not in links:
                links.append(full)
        if len(links) >= limit:
            break
    print(f"Ditemukan {len(links)} link artikel.")
    return links


# ---------- Ekstrak data ----------
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

    return {"judul": title, "ringkasan": make_summary(description, content), "link": url}


# ---------- Simpan CSV ----------
def save_csv(results):
    path = CSV_PATH
    try:
        f = open(path, "w", newline="", encoding="utf-8-sig")
    except PermissionError:
        path = CSV_PATH.with_name(f"hasil_berita_{int(time.time())}.csv")
        print("File utama sedang terbuka, disimpan ke file baru.")
        f = open(path, "w", newline="", encoding="utf-8-sig")
    with f:
        w = csv.DictWriter(f, fieldnames=["judul", "ringkasan", "link"])
        w.writeheader()
        w.writerows(results)
    print(f"Tersimpan di: {path} ({len(results)} baris)")


# ---------- Program utama ----------
def main():
    if "email-kamu" in EMAIL:
        print("Ganti dulu nilai EMAIL dengan emailmu yang aktif.")
        return

    urls = list(EXTRA_URLS)
    for link in collect_links(INDEX_URL, MAX_ARTICLES):
        if link not in urls:
            urls.append(link)
    urls = urls[:MAX_ARTICLES]

    if not urls:
        print("Tidak ada link artikel. Isi EXTRA_URLS secara manual.")
        return

    results = []
    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] {url}")
        html = get_page(url)
        if html:
            item = parse_article(html, url)
            if item:
                results.append(item)
                print("  Judul:", item["judul"])

    if not results:
        print("Tidak ada data yang berhasil dikumpulkan.")
        return
    save_csv(results)


if __name__ == "__main__":
    main()