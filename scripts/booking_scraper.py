import os
import time
import random
import pandas as pd
from urllib.parse import quote
from playwright.sync_api import sync_playwright

CSV_PATH = "overrides/todo_517.csv"
OUT_CSV = "overrides/todo_517_booking.csv"

def extract_from_booking(page, hotel_name):
    try:
        # Wait for the property cards to load
        page.wait_for_selector('[data-testid="property-card"]', timeout=15000)
    except Exception as e:
        print(f"Timeout waiting for property cards for {hotel_name}")
        return None, None
    
    # Get the first property card
    cards = page.locator('[data-testid="property-card"]')
    count = cards.count()
    if count == 0:
        return None, None
        
    for i in range(min(3, count)):
        card = cards.nth(i)
        
        # Get title
        title_locator = card.locator('[data-testid="title"]')
        if title_locator.count() > 0:
            title = title_locator.inner_text().strip()
            
            # Simple check if it's the right hotel (can be enhanced)
            # Sometimes booking adds suffixes or different names, so we just take the first one if it's a close match or if it's the very first result.
            
            # Extract price
            price_locator = card.locator('[data-testid="price-and-discounted-price"]')
            if price_locator.count() > 0:
                price_text = price_locator.inner_text().strip()
                # price_text might look like "TWD 2,249"
                price_num = "".join(filter(str.isdigit, price_text))
                if price_num:
                    return int(price_num), f"Booking ({title})"
            
            # If the first card has no price (e.g. fully booked), we should probably return None
            # because the next cards are usually "recommended alternatives"
            if i == 0:
                print(f"First card '{title}' has no price (might be full).")
                return None, None
                
    return None, None

def run_scraper():
    try:
        df = pd.read_csv(CSV_PATH, encoding='utf-8-sig')
    except Exception:
        df = pd.read_csv(CSV_PATH, encoding='utf-8')
        
    poc_df = df.head(10).copy()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="zh-TW",
            timezone_id="Asia/Taipei"
        )
        page = context.new_page()
        
        for idx, row in poc_df.iterrows():
            hotel_name = row['旅宿名稱']
            print(f"Processing [{idx}] {hotel_name}...")
            
            query = quote(hotel_name)
            url = f"https://www.booking.com/searchresults.zh-tw.html?ss={query}&checkin=2026-09-01&checkout=2026-09-02&group_adults=2&no_rooms=1"
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                # Random delay to prevent blocking
                time.sleep(random.uniform(2, 4))
                
                price, platform = extract_from_booking(page, hotel_name)
                print(f"  -> Found: {price} at {platform}")
                
                if price:
                    poc_df.at[idx, '平日雙人房價'] = price
                    poc_df.at[idx, '來源平台'] = "Booking.com"
            except Exception as e:
                print(f"  -> Error: {e}")
                
        browser.close()
        
    poc_df.to_csv(OUT_CSV, index=False, encoding='utf-8-sig')
    print(f"Saved results to {OUT_CSV}")

if __name__ == "__main__":
    run_scraper()
