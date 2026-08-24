import os
import time
import random
import difflib
import pandas as pd
from urllib.parse import quote
from playwright.sync_api import sync_playwright
import sys

# Ensure stdout is flushed immediately
sys.stdout.reconfigure(line_buffering=True)

CSV_PATH = "overrides/todo_517.csv"

def is_name_match(name1, name2):
    n1 = name1.replace("民宿", "").replace("大飯店", "").replace("飯店", "").replace("旅館", "").replace(" ", "").lower()
    n2 = name2.replace("民宿", "").replace("大飯店", "").replace("飯店", "").replace("旅館", "").replace(" ", "").lower()
    if not n1 or not n2:
        return False
    if n1 in n2 or n2 in n1:
        return True
    ratio = difflib.SequenceMatcher(None, n1, n2).ratio()
    return ratio > 0.5

def extract_from_booking(page, hotel_name):
    try:
        page.wait_for_selector('[data-testid="property-card"]', timeout=5000)
    except Exception:
        return None, None
    
    cards = page.locator('[data-testid="property-card"]')
    count = cards.count()
    if count == 0:
        return None, None
        
    for i in range(min(3, count)):
        card = cards.nth(i)
        title_locator = card.locator('[data-testid="title"]').first
        try:
            title = title_locator.inner_text(timeout=2000).strip()
        except Exception:
            continue
            
        if is_name_match(hotel_name, title):
            price_locator = card.locator('[data-testid="price-and-discounted-price"]').first
            try:
                price_text = price_locator.inner_text(timeout=2000).strip()
                price_num = "".join(filter(str.isdigit, price_text))
                if price_num:
                    return int(price_num), f"Booking.com"
            except Exception:
                pass
            return None, None
    return None, None

def run_scraper():
    try:
        df = pd.read_csv(CSV_PATH, encoding='utf-8-sig', keep_default_na=False)
    except Exception:
        df = pd.read_csv(CSV_PATH, encoding='utf-8', keep_default_na=False)
    
    with sync_playwright() as p:
        def get_browser_page():
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="zh-TW",
                timezone_id="Asia/Taipei"
            )
            context.set_default_timeout(10000)
            page = context.new_page()
            return browser, page
            
        browser, page = get_browser_page()
        processed_since_restart = 0
        
        for idx, row in df.iterrows():
            if row['平日雙人房價'] != "":
                continue
                
            hotel_name = str(row['旅宿名稱']).strip()
            print(f"[{idx+1}/517] Processing {hotel_name}...")
            
            query = quote(hotel_name)
            url = f"https://www.booking.com/searchresults.zh-tw.html?ss={query}&checkin=2026-09-01&checkout=2026-09-02&group_adults=2&no_rooms=1"
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=12000)
                time.sleep(random.uniform(0.5, 1.5))
                
                price, platform = extract_from_booking(page, hotel_name)
                
                if price:
                    print(f"  -> Found: {price} at {platform}")
                    df.at[idx, '平日雙人房價'] = str(price)
                    df.at[idx, '來源平台'] = platform
                else:
                    print(f"  -> Not found or fully booked.")
                    df.at[idx, '平日雙人房價'] = "查無"
                    df.at[idx, '來源平台'] = ""
            except Exception as e:
                print(f"  -> Error: {e}")
                df.at[idx, '平日雙人房價'] = "查無"
                df.at[idx, '來源平台'] = ""
                
            processed_since_restart += 1
            if processed_since_restart >= 20:
                print("Restarting browser to prevent memory leak/hang...")
                try:
                    browser.close()
                except:
                    pass
                browser, page = get_browser_page()
                processed_since_restart = 0
                
            if (idx + 1) % 5 == 0:
                df.to_csv(CSV_PATH, index=False, encoding='utf-8-sig')
                
        try:
            browser.close()
        except:
            pass
            
    df.to_csv(CSV_PATH, index=False, encoding='utf-8-sig')
    print("Finished all 517 rows.")

if __name__ == "__main__":
    run_scraper()
