import time
from playwright.sync_api import sync_playwright

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://www.google.com/travel/search?q=%E5%A4%AA%E5%AD%90%E8%A1%8C%E6%97%85&checkin=2026-09-01&checkout=2026-09-02&adults=2")
    page.wait_for_timeout(3000)
    
    body_text = page.locator("body").inner_text()
    with open("google_travel.txt", "w", encoding="utf-8") as f:
        f.write(body_text)
    
    # Check for pricing elements
    prices = page.locator("text=NT$").all_inner_texts()
    with open("google_prices.txt", "w", encoding="utf-8") as f:
        f.write(str(prices))
    
    browser.close()

with sync_playwright() as playwright:
    run(playwright)
