# -*- coding: utf-8 -*-
"""用 Google Places API (New) 補上第三種價格訊號與評價。

為什麼需要：官方開放資料的「定價」是牌價，實測中位數是實際優惠價的 1.9 倍、
最誇張 12.5 倍（有業者直說「還沒收到公文先隨便填」）。Places API 的
priceLevel／priceRange 與評分可以當作獨立的對照。

為什麼不爬 Google Maps 網頁：那裡的房價是綁特定日期的 OTA 即時報價，不是旅宿的
固定屬性，凍進每週更新的靜態檔只會再造一個假精確的欄位；而且 1,796 筆的自動查詢
必然撞上機器人偵測。官方 API 拿到的 priceLevel 是穩定的價位帶，才適合這個用途。

金鑰放法（擇一，都不會進版控）：
  1. 環境變數  GOOGLE_MAPS_API_KEY
  2. 檔案      cache/google_api_key.txt（只放金鑰本身，已在 .gitignore）

用法：
  python scripts/places.py --dry-run     # 只印出要查什麼，不打 API
  python scripts/places.py --limit 20    # 先查 20 筆看看比對品質
  python scripts/places.py               # 全部（只查快取裡沒有的）
"""
import os, sys, json, time, math, argparse
import requests
from config import ROOT, RAW, CACHE, jload, jdump, norm_name, norm_phones

KEY_FILE = os.path.join(CACHE, "google_api_key.txt")
PLACES_CACHE = os.path.join(CACHE, "places.json")
ENDPOINT = "https://places.googleapis.com/v1/places:searchText"

# 只要這些欄位，欄位越少計費層級越低
FIELD_MASK = ",".join([
    "places.id", "places.displayName", "places.formattedAddress", "places.location",
    "places.rating", "places.userRatingCount", "places.priceLevel", "places.priceRange",
    "places.nationalPhoneNumber", "places.googleMapsUri", "places.businessStatus",
])

PRICE_LEVEL = {
    "PRICE_LEVEL_FREE": 0,
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}

MATCH_RADIUS_M = 400          # 座標吻合的容忍距離
RATE_SLEEP = 0.12             # 每秒約 8 次，遠低於 Places 的上限


def load_key():
    k = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if not k and os.path.exists(KEY_FILE):
        k = open(KEY_FILE, encoding="utf-8").read().strip()
    return k


def meters(lat1, lon1, lat2, lon2):
    r, p = 6371000.0, math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2 +
         math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


def verify(stay, place):
    """店名 + 地址（座標）+ 電話三選一吻合才採用，並記下是靠什麼比中的。
    Google 有時會回傳附近的另一家旅宿，不驗證會把價格掛到錯的店上。"""
    reasons = []

    loc = place.get("location") or {}
    if loc.get("latitude") and stay.get("lat"):
        d = meters(stay["lat"], stay["lng"], loc["latitude"], loc["longitude"])
        if d <= MATCH_RADIUS_M:
            reasons.append("distance:%dm" % int(d))
    else:
        d = None

    ours = set(stay.get("phones") or [])
    theirs = set(norm_phones(place.get("nationalPhoneNumber")))
    if ours & theirs:
        reasons.append("phone")

    a, b = norm_name(stay["name"]), norm_name((place.get("displayName") or {}).get("text"))
    if a and b and (a == b or a in b or b in a):
        reasons.append("name")

    return reasons, d


def search(stay, key, session):
    body = {
        "textQuery": "%s %s" % (stay["name"], stay.get("address") or stay.get("city", "")),
        "languageCode": "zh-TW",
        "regionCode": "TW",
        "maxResultCount": 3,
    }
    if stay.get("lat"):
        body["locationBias"] = {"circle": {
            "center": {"latitude": stay["lat"], "longitude": stay["lng"]},
            "radius": 2000.0}}

    r = session.post(ENDPOINT, json=body, timeout=30, headers={
        "X-Goog-Api-Key": key, "X-Goog-FieldMask": FIELD_MASK,
        "Content-Type": "application/json"})
    if r.status_code != 200:
        return None, "HTTP %s %s" % (r.status_code, r.text[:200])
    return r.json().get("places") or [], None


def pick(stay, places):
    """在最多 3 筆候選裡挑驗證通過、且理由最多的那個。"""
    best, best_reasons, best_d = None, [], None
    for p in places:
        reasons, d = verify(stay, p)
        if not reasons:
            continue
        if len(reasons) > len(best_reasons):
            best, best_reasons, best_d = p, reasons, d
    return best, best_reasons, best_d


def compact(place, reasons, d):
    pr = place.get("priceRange") or {}
    return {
        "place_id": place.get("id"),
        "name": (place.get("displayName") or {}).get("text"),
        "address": place.get("formattedAddress"),
        "rating": place.get("rating"),
        "reviews": place.get("userRatingCount"),
        "price_level": PRICE_LEVEL.get(place.get("priceLevel")),
        "price_start": (pr.get("startPrice") or {}).get("units"),
        "price_end": (pr.get("endPrice") or {}).get("units"),
        "currency": (pr.get("startPrice") or {}).get("currencyCode"),
        "maps_uri": place.get("googleMapsUri"),
        "status": place.get("businessStatus"),
        "match": reasons,
        "match_distance_m": int(d) if d is not None else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只印查詢字串，不打 API")
    ap.add_argument("--limit", type=int, default=0, help="只處理前 N 筆（試跑用）")
    ap.add_argument("--refresh", action="store_true", help="連已快取的也重查")
    args = ap.parse_args()

    blob = jload(os.path.join(RAW, "merged.json"))
    if not blob:
        raise SystemExit("找不到 raw/merged.json，請先跑 enrich.py")
    stays = blob["stays"]
    cache = jload(PLACES_CACHE, {}) or {}

    todo = [s for s in stays if args.refresh or s["id"] not in cache]
    if args.limit:
        todo = todo[:args.limit]

    print("[Places] 共 %d 家，已快取 %d 家，這次要查 %d 家"
          % (len(stays), len(cache), len(todo)), flush=True)

    if args.dry_run:
        for s in todo[:20]:
            print("  查詢字串: %s %s" % (s["name"], s.get("address") or s.get("city")))
        print("  （--dry-run，沒有實際呼叫 API）")
        return

    if not todo:
        print("[Places] 沒有新的要查，直接結束")
        return

    key = load_key()
    if not key:
        raise SystemExit(
            "找不到 API 金鑰。請設環境變數 GOOGLE_MAPS_API_KEY，"
            "或把金鑰寫進 cache/google_api_key.txt（已在 .gitignore，不會進版控）")

    session = requests.Session()
    stat = {"matched": 0, "no_result": 0, "rejected": 0, "error": 0}
    errors = []

    for i, s in enumerate(todo, 1):
        places, err = search(s, key, session)
        if err:
            stat["error"] += 1
            errors.append((s["name"], err))
            if len(errors) >= 5:
                print("[Places] 連續失敗過多，中止以免浪費額度：")
                for n, e in errors[-5:]:
                    print("   ", n, e)
                break
            time.sleep(2)
            continue

        if not places:
            cache[s["id"]] = {"match": [], "note": "no_result"}
            stat["no_result"] += 1
        else:
            best, reasons, d = pick(s, places)
            if best:
                cache[s["id"]] = compact(best, reasons, d)
                stat["matched"] += 1
            else:
                cache[s["id"]] = {"match": [], "note": "rejected",
                                  "candidates": [(p.get("displayName") or {}).get("text")
                                                 for p in places]}
                stat["rejected"] += 1

        if i % 50 == 0:
            jdump(cache, PLACES_CACHE)
            print("  %d/%d  %s" % (i, len(todo), stat), flush=True)
        time.sleep(RATE_SLEEP)

    jdump(cache, PLACES_CACHE)

    matched = [v for v in cache.values() if v.get("place_id")]
    with_level = [v for v in matched if v.get("price_level") is not None]
    with_range = [v for v in matched if v.get("price_start")]
    with_rating = [v for v in matched if v.get("rating")]
    print()
    print("[Places] %s" % stat)
    print("[Places] 快取共 %d 家：比中 %d、有價位帶 %d、有實際價格區間 %d、有評分 %d"
          % (len(cache), len(matched), len(with_level), len(with_range), len(with_rating)))
    if errors:
        print("[Places] 有 %d 筆失敗，例如：%s" % (len(errors), errors[0]))


if __name__ == "__main__":
    main()
