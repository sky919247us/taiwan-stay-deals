# -*- coding: utf-8 -*-
"""用 SerpApi 的 Google Hotels API 取得各訂房平台的平日房價（參考價）。

為什麼走這條：Google 地圖／搜尋上確實看得到各訂房平台的房價，但那是即時
廣告版位，自己寫程式大量查會撞機器人偵測。SerpApi 是商業服務，提供官方
API，合規責任在他們身上，我們只是正常呼叫 API。

為什麼要指定日期：那些報價綁特定入住日，所以固定查「補助期間內的一個平日」
（週日至週四、避開連假），拿到的才是對本站使用者有意義的數字。

重要：這個價格是**訂房平台報價，多數不能折抵國旅補助**（補助須直接向官網
或電話訂房）。所以存成獨立欄位 ota_price，前端要清楚標示，不可以跟
「業者自報的補助平日價」混為一談。

金鑰：環境變數 SERPAPI_KEY，或 cache/serpapi_key.txt（已 gitignore）。

用法：
  python scripts/otaprice.py --dry-run        # 看要查什麼、幾次，不打 API
  python scripts/otaprice.py --limit 5        # 先試 5 家看比對品質
  python scripts/otaprice.py --budget 240     # 這輪最多打 240 次（顧免費額度）
  python scripts/otaprice.py --report
"""
import os, re, sys, json, time, datetime, argparse
import requests
from config import ROOT, RAW, CACHE, jload, jdump, norm_name

KEY_FILE = os.path.join(CACHE, "serpapi_key.txt")
OTA_CACHE = os.path.join(CACHE, "otaprice.json")
ENDPOINT = "https://serpapi.com/search"

# 補助期間與排除的連假，跟前端那顆「即時房價」按鈕用同一組規則
SUBSIDY_START = datetime.date(2026, 9, 1)
SUBSIDY_END = datetime.date(2026, 11, 30)
HOLIDAY_BLOCKS = [
    (datetime.date(2026, 9, 25), datetime.date(2026, 9, 28)),
    (datetime.date(2026, 10, 9), datetime.date(2026, 10, 11)),
    (datetime.date(2026, 10, 24), datetime.date(2026, 10, 26)),
]


def weekday_in_window():
    """挑補助期間內、今天之後、週日至週四、且非連假的第一天。"""
    d = max(datetime.date.today() + datetime.timedelta(days=3), SUBSIDY_START)
    for _ in range(150):
        if d > SUBSIDY_END:
            return None
        # Python: 週一=0 … 週日=6；補助適用週日至週四
        if d.weekday() in (6, 0, 1, 2, 3) and not any(a <= d <= b for a, b in HOLIDAY_BLOCKS):
            return d
        d += datetime.timedelta(days=1)
    return None


def load_key():
    k = os.environ.get("SERPAPI_KEY", "").strip()
    if not k and os.path.exists(KEY_FILE):
        k = open(KEY_FILE, encoding="utf-8-sig", errors="replace").read().strip()
    return re.sub(r"\s+", "", k)


def query_of(s):
    return "%s %s%s" % (s["name"], s.get("city", ""), s.get("town", ""))


def pick(stay, props):
    """SerpApi 會回一串附近飯店，名稱對不上就不要，免得把價格掛到隔壁家。"""
    target = norm_name(stay["name"])
    for p in props or []:
        other = norm_name(p.get("name") or "")
        if not other:
            continue
        if other == target or target in other or other in target:
            return p
    return None


def cheapest(prop):
    """取各平台裡最低的每晚價；SerpApi 的欄位在不同結果型態下不一致，逐個試。"""
    best, who = None, ""
    for src in (prop.get("prices") or []):
        rate = (src.get("rate_per_night") or {})
        v = rate.get("extracted_lowest") or rate.get("extracted_before_taxes_fees")
        if isinstance(v, (int, float)) and 300 <= v <= 60000:
            if best is None or v < best:
                best, who = int(v), src.get("source") or ""
    if best is None:
        rate = (prop.get("rate_per_night") or {})
        v = rate.get("extracted_lowest")
        if isinstance(v, (int, float)) and 300 <= v <= 60000:
            best, who = int(v), "Google"
    return best, who


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--budget", type=int, default=0, help="這輪最多打幾次 API")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    blob = jload(os.path.join(RAW, "merged.json"))
    if not blob:
        raise SystemExit("找不到 raw/merged.json，請先跑 enrich.py")
    cache = jload(OTA_CACHE, {}) or {}

    if args.report:
        got = [v for v in cache.values() if v.get("price")]
        print("已查 %d 家，取得平台報價 %d 家" % (len(cache), len(got)))
        for v in sorted(got, key=lambda x: x["price"])[:20]:
            print("  %6d  %-18s %-12s %s" % (v["price"], v.get("name", "")[:18],
                                             v.get("source", ""), v.get("date", "")))
        return

    checkin = weekday_in_window()
    if not checkin:
        raise SystemExit("補助期間內已經找不到可用的平日，不需要再查了")
    checkout = checkin + datetime.timedelta(days=1)

    # 只查「四種來源都拿不到房價」的，其餘不浪費額度
    from manual import load_overrides
    man = load_overrides()
    web = jload(os.path.join(CACHE, "webprice.json"), {}) or {}
    plan = jload(os.path.join(CACHE, "planprice.json"), {}) or {}
    js = jload(os.path.join(CACHE, "webprice_js.json"), {}) or {}

    def has_price(s):
        i = s["id"]
        if man.get(i) or s.get("weekday_price"):
            return True
        for c in (plan, web, js):
            v = c.get(i) or {}
            if v.get("price") and v.get("basis") == "weekday":
                return True
        return False

    todo = [s for s in blob["stays"]
            if not has_price(s) and (args.refresh or s["id"] not in cache)]
    if args.limit:
        todo = todo[:args.limit]
    if args.budget:
        todo = todo[:args.budget]

    print("[平台報價] 入住日 %s（週%s）／退房 %s"
          % (checkin, "一二三四五六日"[checkin.weekday()], checkout))
    print("[平台報價] 待查 %d 家，已快取 %d 家" % (len(todo), len(cache)), flush=True)

    if args.dry_run:
        for s in todo[:10]:
            print("  查詢：%s" % query_of(s))
        print("  （--dry-run，沒有實際呼叫 API；本輪會用掉 %d 次額度）" % len(todo))
        return
    if not todo:
        return

    key = load_key()
    if not key:
        raise SystemExit(
            "找不到 SerpApi 金鑰。請設環境變數 SERPAPI_KEY，或把金鑰寫進 "
            "cache/serpapi_key.txt（已 gitignore，不會進版控）")

    session = requests.Session()
    stat = {"price": 0, "no_match": 0, "no_price": 0, "error": 0}
    errors = 0

    for i, s in enumerate(todo, 1):
        rec = {"name": s["name"], "date": str(checkin)}
        try:
            r = session.get(ENDPOINT, timeout=60, params={
                "engine": "google_hotels", "q": query_of(s),
                "check_in_date": str(checkin), "check_out_date": str(checkout),
                "adults": 2, "currency": "TWD", "gl": "tw", "hl": "zh-tw",
                "api_key": key,
            })
            if r.status_code != 200:
                rec["note"] = "http_%s" % r.status_code
                stat["error"] += 1
                errors += 1
                if errors >= 5:
                    print("[平台報價] 連續失敗過多，中止以免浪費額度")
                    break
            else:
                data = r.json()
                prop = pick(s, data.get("properties"))
                if not prop:
                    rec["note"] = "no_match"
                    stat["no_match"] += 1
                else:
                    price, who = cheapest(prop)
                    if price:
                        rec.update({"price": price, "source": who,
                                    "matched": prop.get("name"),
                                    "rating": prop.get("overall_rating")})
                        stat["price"] += 1
                    else:
                        rec["note"] = "no_price"
                        stat["no_price"] += 1
        except Exception as e:
            rec["note"] = "error:%s" % type(e).__name__
            stat["error"] += 1

        cache[s["id"]] = rec
        jdump(cache, OTA_CACHE)
        print("  %3d/%d %-18s %s" % (i, len(todo), s["name"][:18],
                                     rec.get("price") or rec.get("note")), flush=True)
        time.sleep(1.2)          # 免費方案是每小時 50 次，別打太快

    print("\n[平台報價] %s" % stat)
    print("[平台報價] 這輪用掉約 %d 次額度" % sum(stat.values()))


if __name__ == "__main__":
    main()
