import time
from urllib.parse import quote
from playwright.sync_api import sync_playwright

def run_debug():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            locale="zh-TW",
            timezone_id="Asia/Taipei"
        )
        page = context.new_page()
        
        hotel_name = "太子行旅"
        query = quote(hotel_name)
        url = f"https://www.google.com/travel/search?q={query}&checkin=2026-09-01&checkout=2026-09-02&adults=2"
        
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(5000)
        
        page.screenshot(path="google_travel.png", full_page=True)
        
        browser.close()

if __name__ == "__main__":
    run_debug()
