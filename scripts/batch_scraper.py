import os
import sys
import time
import random
import difflib
import pandas as pd
from urllib.parse import quote
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(line_buffering=True)

def is_name_match(name1, name2):
    n1 = name1.replace("民宿", "").replace("大飯店", "").replace("飯店", "").replace("旅館", "").replace(" ", "").lower()
    n2 = name2.replace("民宿", "").replace("大飯店", "").replace("飯店", "").replace("旅館", "").replace(" ", "").lower()
    if not n1 or not n2:
        return False
    if n1 in n2 or n2 in n1:
        return True
    ratio = difflib.SequenceMatcher(None, n1, n2).ratio()
    return ratio > 0.5

def extract_from_booking(page, hotel_name, min_price, max_price):
    try:
        page.wait_for_selector('[data-testid="property-card"]', timeout=8000)
    except Exception:
        # Check if it says no results
        body_text = page.locator("body").inner_text()
        if "找不到符合" in body_text or "無空房" in body_text or "售完" in body_text:
            return None, None, "當日售完"
        return None, None, "平台無此旅宿"
    
    cards = page.locator('[data-testid="property-card"]')
    count = cards.count()
    if count == 0:
        return None, None, "平台無此旅宿"
        
    for i in range(min(5, count)):
        card = cards.nth(i)
        title_locator = card.locator('[data-testid="title"]').first
        try:
            title = title_locator.inner_text(timeout=2000).strip()
        except Exception:
            continue
            
        if is_name_match(hotel_name, title):
            # Check price
            price_locator = card.locator('[data-testid="price-and-discounted-price"]').first
            price_num = 0
            try:
                price_text = price_locator.inner_text(timeout=2000).strip()
                price_digits = "".join(filter(str.isdigit, price_text))
                if price_digits:
                    price_num = int(price_digits)
            except Exception:
                return None, None, "當日售完" # Found hotel but no price means sold out
                
            if price_num == 0:
                return None, None, "當日售完"

            # Check room name
            room_name = "標準雙人房" # Fallback
            room_locator = card.locator('[data-testid="recommended-units"]').first
            try:
                room_text_full = room_locator.inner_text(timeout=2000)
                lines = [line.strip() for line in room_text_full.split('\n') if line.strip()]
                if lines:
                    room_name = lines[0] # Usually the first line is the room type
            except Exception:
                pass
            
            # Exclusion keywords for non-double rooms
            exclude_keywords = ["四人", "三人", "家庭", "六人", "八人", "包棟", "宿舍", "單人"]
            for kw in exclude_keywords:
                if kw in room_name:
                    return None, room_name, "僅有其他房型"

            # Validate price bounds
            if min_price > 0 and max_price > 0:
                if price_num < min_price or price_num > max_price:
                    return None, room_name, "僅有其他房型"
                    
            return price_num, room_name, "已查到"
            
    return None, None, "平台無此旅宿"

def run_scraper(csv_path):
    print(f"Starting scrape for {csv_path}...")
    try:
        df = pd.read_csv(csv_path, encoding='utf-8-sig', keep_default_na=False)
    except Exception:
        df = pd.read_csv(csv_path, encoding='utf-8', keep_default_na=False)
        
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
            if str(row.get('結果', '')).strip() != "":
                continue # Skip already processed
                
            hotel_name = str(row['旅宿名稱']).strip()
            print(f"[{idx+1}/{len(df)}] Processing {hotel_name}...")
            
            min_price = 0
            max_price = 0
            try:
                min_price = int(row.get('合理價格下限', 0))
                max_price = int(row.get('合理價格上限', 0))
            except:
                pass
            
            query = quote(hotel_name)
            url = f"https://www.booking.com/searchresults.zh-tw.html?ss={query}&checkin=2026-09-01&checkout=2026-09-02&group_adults=2&no_rooms=1"
            
            result_status = "查詢失敗"
            final_price = ""
            final_room = ""
            final_platform = ""
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
                time.sleep(random.uniform(1.0, 2.0))
                
                price, room_name, status = extract_from_booking(page, hotel_name, min_price, max_price)
                
                result_status = status
                if status == "已查到" and price:
                    final_price = price
                    final_room = room_name
                    final_platform = "Booking.com"
                elif status == "僅有其他房型":
                    final_room = room_name if room_name else ""
                    
            except Exception as e:
                print(f"  -> Error: {e}")
                result_status = "查詢失敗"
                
            print(f"  -> {result_status} | {final_price} | {final_room}")
            
            df.at[idx, '平日雙人房價'] = final_price
            df.at[idx, '房型名稱'] = final_room
            df.at[idx, '來源平台'] = final_platform
            df.at[idx, '結果'] = result_status
            df.at[idx, '查核日期'] = '2026-08-24'
            
            processed_since_restart += 1
            if processed_since_restart >= 10:
                print("Restarting browser to prevent memory leak/hang...")
                try:
                    browser.close()
                except:
                    pass
                browser, page = get_browser_page()
                processed_since_restart = 0
                
            # Save every row to avoid data loss
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            
        try:
            browser.close()
        except:
            pass
            
    print(f"Finished {csv_path}.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_scraper(sys.argv[1])
    else:
        print("Please provide csv path.")
