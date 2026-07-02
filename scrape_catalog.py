"""
scrape_catalog.py (fixed) -- renders the page with a real headless browser
so JavaScript-loaded content actually shows up, then extracts rows exactly
as the live site presents them (no guessed/old URL patterns).

RUN debug_inspect.py FIRST and look at debug_screenshot.png. If a real
table of assessments is visible there, this script's generic table-parsing
should work as-is. If the screenshot shows something unexpected (e.g. a
"select a filter first" state, or a tab you need to click), open
debug_page.html, search for "Individual Test Solutions", and tell me what
you see -- we'll adjust the selectors together rather than guessing blind.

Setup (once):
    pip install playwright requests beautifulsoup4
    playwright install chromium

Run:
    python scrape_catalog.py
"""
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE = "https://www.shl.com"
LIST_url = "https://www.shl.com/solutions/products/product-catalog/"
PAGE_SIZE = 12
MAX_PAGES = 40
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


def dismiss_cookie_banner(page):
    for text in ["Continue", "Accept", "I understand and wish to continue"]:
        try:
            btn = page.get_by_text(text, exact=False).first
            if btn.is_visible(timeout=1200):
                btn.click()
                page.wait_for_timeout(800)
        except Exception:
            pass


def render_listing_html(page, start: int) -> str:
    url = f"{LIST_url}?start={start}&type=1"
    page.goto(url, wait_until="networkidle", timeout=45000)
    dismiss_cookie_banner(page)
    page.wait_for_timeout(2500)  # let any AJAX table finish rendering
    return page.content()


def parse_test_type_codes(cell) -> list:
    text = cell.get_text(" ", strip=True)
    codes = re.findall(r"\b[A-Z]{1,2}\b", text)
    return codes if codes else ([text] if text else [])


def has_yes_marker(cell) -> bool:
    if cell is None:
        return False
    classes = " ".join(cell.get("class", []))
    if "yes" in classes.lower():
        return True
    if cell.find(class_=re.compile("yes", re.I)):
        return True
    return bool(cell.find("span", class_=re.compile("circle", re.I)))


def parse_rows(html: str) -> list:
    """Generic table-row parser: works whatever the current CSS classes are,
    as long as rows are <tr> containing a link to the assessment."""
    soup = BeautifulSoup(html, "html.parser")
    rows_out = []
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            link = tr.find("a", href=True)
            if not link:
                continue
            name = link.get_text(strip=True)
            if not name:
                continue
            url = urljoin(BASE, link["href"])
            cells = tr.find_all(["td", "th"])
            remote_testing, adaptive_irt, test_type = False, False, []
            for c in cells[1:]:
                cls = " ".join(c.get("class", []))
                txt = c.get_text(" ", strip=True)
                if "remote" in cls.lower():
                    remote_testing = has_yes_marker(c)
                elif "adaptive" in cls.lower() or "irt" in cls.lower():
                    adaptive_irt = has_yes_marker(c)
                elif "type" in cls.lower() or re.fullmatch(r"[A-Z](\s[A-Z])*", txt or ""):
                    test_type = parse_test_type_codes(c)
            rows_out.append({
                "name": name, "url": url,
                "remote_testing": remote_testing,
                "adaptive_irt": adaptive_irt,
                "test_type": test_type,
            })
    return rows_out


def fetch_description(url: str) -> tuple:
    """Fresh URLs pulled straight from the rendered table should be the
    site's real current detail pages (not stale/guessed ones), so a plain
    request usually works here even though the listing page needed JS."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        desc = ""
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            desc = meta["content"].strip()
        text = soup.get_text(" ", strip=True)
        job_levels = []
        m = re.search(r"Job level[s]?:?\s*([A-Za-z ,/\-]+)", text)
        if m:
            job_levels = [x.strip() for x in m.group(1).split(",") if x.strip()][:8]
        return desc, job_levels
    except Exception as e:
        print(f"  ! description fetch failed for {url}: {e}")
        return "", []


def main():
    all_items = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=HEADERS["User-Agent"])

        start = 0
        empty_streak = 0
        for _ in range(MAX_PAGES):
            print(f"Rendering start={start} ...")
            html = render_listing_html(page, start)
            rows = parse_rows(html)
            print(f"  got {len(rows)} rows")
            if not rows:
                empty_streak += 1
                if empty_streak >= 2:
                    break
            else:
                empty_streak = 0
                for r in rows:
                    all_items[r["url"]] = r
            start += PAGE_SIZE

        browser.close()

    if not all_items:
        print(
            "\nWARNING: 0 items scraped. Run debug_inspect.py, open "
            "debug_screenshot.png, and check whether a table actually "
            "appears, or whether you need to click a filter/tab first."
        )
        Path("data/catalog.json").write_text("[]", encoding="utf-8")
        return

    print(f"\nFound {len(all_items)} unique assessments. Fetching descriptions...")
    catalog = []
    for i, item in enumerate(all_items.values()):
        desc, job_levels = fetch_description(item["url"])
        catalog.append({
            "id": i,
            "name": item["name"],
            "url": item["url"],
            "remote_testing": item["remote_testing"],
            "adaptive_irt": item["adaptive_irt"],
            "test_type": item["test_type"],
            "test_type_labels": item["test_type"],  # expand with a lookup dict if you want full label text
            "description": desc,
            "job_levels": job_levels,
        })
        if (i + 1) % 25 == 0:
            print(f"  ...{i + 1}/{len(all_items)} done")
        time.sleep(0.3)  # be polite

    out_path = Path("data/catalog.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(catalog)} assessments to {out_path}")


if __name__ == "__main__":
    main()