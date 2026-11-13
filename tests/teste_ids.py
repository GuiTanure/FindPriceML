from playwright.sync_api import sync_playwright
import re

p = sync_playwright().start()
b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
page = b.contexts[0].pages[0]

ids = set()

for a in page.locator("a[href]").all():
    href = a.get_attribute("href") or ""
    for item_id in re.findall(r"[?&]wid=(MLB\d+)", href):
        ids.add(item_id)

print("\n".join(sorted(ids)))

p.stop()