"""
RUN THIS FIRST, before touching scrape_catalog.py.

It opens SHL's catalog page in a real (headless) Chromium browser -- so
JavaScript actually runs -- and saves:
  debug_screenshot.png  -> open this and LOOK at it. Does a table appear?
  debug_page.html       -> the fully rendered HTML, after JS ran.

Setup (run once):
    pip install playwright
    playwright install chromium

Run:
    python debug_inspect.py
"""
from playwright.sync_api import sync_playwright

URL = "https://www.shl.com/solutions/products/product-catalog/?start=0&type=1"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(user_agent=(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ))
    print(f"Navigating to {URL} ...")
    page.goto(URL, wait_until="networkidle", timeout=45000)

    for text in ["Continue", "Accept", "I understand and wish to continue"]:
        try:
            btn = page.get_by_text(text, exact=False).first
            if btn.is_visible(timeout=1500):
                btn.click()
                print(f"Dismissed a banner by clicking '{text}'")
                page.wait_for_timeout(1000)
        except Exception:
            pass

    page.wait_for_timeout(4000)

    page.screenshot(path="debug_screenshot.png", full_page=True)
    html = page.content()
    with open("debug_page.html", "w", encoding="utf-8") as f:
        f.write(html)

    table_count = page.locator("table").count()
    row_count = page.locator("table tr").count()
    print(f"Found {table_count} <table> elements and {row_count} <tr> rows.")
    print("Saved debug_screenshot.png and debug_page.html -- open both and look.")

    browser.close()