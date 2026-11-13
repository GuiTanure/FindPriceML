from playwright.sync_api import sync_playwright

p = sync_playwright().start()
b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
page = b.contexts[0].pages[0]

for a in page.locator("a[href]").all():
    href = a.get_attribute("href") or ""
    if "wid=MLB" in href:
        texto = (a.inner_text() or "").strip().replace("\n", " ")
        print(f"{href.split('wid=')[1].split('&')[0]} | {texto[:120]}")

p.stop()