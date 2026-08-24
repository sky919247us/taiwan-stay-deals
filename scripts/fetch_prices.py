import os
import time
import pandas as pd
from urllib.parse import quote
from playwright.sync_api import sync_playwright

CSV_PATH = "overrides/todo_517.csv"
OUT_CSV = "overrides/todo_517_poc.csv"

def extract_prices_from_page(page):
    try:
        page.wait_for_timeout(4000)
    except Exception as e:
        pass
    
    links = page.locator("a").all_inner_texts()
    candidates = []
    
    for text in links:
        if "NT$" in text:
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            if len(lines) >= 2:
                ota = lines[0]
                price_str = ""
                for line in lines:
                    if "NT$" in line:
                        price_str = line
                        break
                
                price_num = "".join(filter(str.isdigit, price_str))
                if price_num:
                    candidates.append({
                        "ota": ota,
                        "price": int(price_num)
                    })
    
    if not candidates:
        return None, None
    
    candidates.sort(key=lambda x: x["price"])
    best = candidates[0]
    return best["price"], best["ota"]

def run_poc():
    # Fix the encoding to utf-8 (or utf-8-sig)
    try:
        df = pd.read_csv(CSV_PATH, encoding='utf-8-sig')
    except Exception:
        df = pd.read_csv(CSV_PATH, encoding='utf-8')
        
    poc_df = df.head(5).copy()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            locale="zh-TW",
            timezone_id="Asia/Taipei"
        )
        page = context.new_page()
        
        for idx, row in poc_df.iterrows():
            hotel_name = row['旅宿名稱']
            print(f"Processing [{idx}] {hotel_name}...")
            
            query = quote(hotel_name)
            url = f"https://www.google.com/travel/search?q={query}&checkin=2026-09-01&checkout=2026-09-02&adults=2"
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                price, platform = extract_prices_from_page(page)
                print(f"  -> Found: {price} at {platform}")
                
                if price:
                    poc_df.at[idx, '平日雙人房價'] = price
                    poc_df.at[idx, '來源平台'] = platform
            except Exception as e:
                print(f"  -> Error: {e}")
                
        browser.close()
        
    poc_df.to_csv(OUT_CSV, index=False, encoding='utf-8-sig')
    print(f"Saved POC results to {OUT_CSV}")

if __name__ == "__main__":
    run_poc()
