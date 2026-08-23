# -*- coding: utf-8 -*-
"""把業者自填的「方案內容」純文字，抽成可以篩選的結構化欄位。

官網之所以無法用方案內容過濾，就是因為這欄是自由文字。抽不出來的就留空，不猜。
"""
import os, re, json, collections
from config import RAW, jload, jdump

# 「平價優質旅宿」類別的方案內容格式非常固定：平日雙人房售價：1600(無早餐)
RE_WEEKDAY_PRICE = re.compile(r"平日雙人房(?:售價|價格|房價)?[：: ]*\$?([\d,]{3,6})")
RE_MONEY = re.compile(r"(?:\$|NT\$?|新台幣)?\s?([\d,]{3,6})\s?(?:元|塊)?")
RE_PERIOD = re.compile(r"(20\d{2})[/\-.年](\d{1,2})[/\-.月](\d{1,2})")

SUBSIDY_AMOUNTS = {800, 1000, 1200, 1500}

KEY_BIRTHDAY = ("生日券", "生日住宿金", "壽星", "生日金")
KEY_WEEKDAY = ("平日", "週日至週四", "周日至周四", "週一至週四", "周一至周四")
KEY_HOLIDAY_EXCL = ("不含國定假日", "連續假期不適用", "連假不適用", "不適用連續假期",
                    "國定假日及其連續假期", "假日不適用")
KEY_BREAKFAST = ("含早餐", "附早餐", "早餐", "早")
KEY_NO_BREAKFAST = ("無早餐", "不含早餐")
KEY_PERK = ("贈", "加碼", "免費", "招待", "升等", "折扣", "優惠價", "小禮", "禮物", "點數")
KEY_PARKING = ("停車", "車位")
KEY_HOTSPRING = ("溫泉", "泡湯", "湯屋")
KEY_PET = ("寵物", "毛小孩")
KEY_WHOLE = ("包棟", "整棟")

CHANNELS = [
    ("line", ("line", "ＬＩＮＥ", "賴")),
    ("official", ("官網", "官方網站", "官方訂房")),
    ("phone", ("電話訂房", "來電", "電洽", "致電")),
    ("fb", ("facebook", "fb", "臉書", "粉絲")),
    ("ota", ("訂房平台", "agoda", "booking", "asiayo", "易遊網", "klook")),
]

EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️⬀-⯿]+")


def clean(text):
    t = EMOJI.sub(" ", text or "")
    t = re.sub(r"[ \t　]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def money_values(text):
    out = []
    for m in RE_MONEY.finditer(text or ""):
        try:
            v = int(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if 300 <= v <= 60000:
            out.append(v)
    return out


def latest_period(plans):
    """多個方案取最晚的優惠期限，格式統一成 YYYY-MM-DD。"""
    best = ""
    for p in plans:
        m = RE_PERIOD.search(p.get("period") or "")
        if m:
            iso = "%s-%02d-%02d" % (m.group(1), int(m.group(2)), int(m.group(3)))
            best = max(best, iso)
    return best


def analyse(rec):
    texts = [p.get("text") or "" for p in rec["plans"]]
    blob = "\n".join(texts)
    low = blob.lower()

    weekday_price = 0
    for t in texts:
        m = RE_WEEKDAY_PRICE.search(t)
        if m:
            v = int(m.group(1).replace(",", ""))
            if 300 <= v <= 60000:
                weekday_price = v if not weekday_price else min(weekday_price, v)

    discounts = sorted({v for v in money_values(blob) if v in SUBSIDY_AMOUNTS})
    prices = [v for v in money_values(blob) if v not in SUBSIDY_AMOUNTS]

    channels = [key for key, words in CHANNELS if any(w in low for w in words)]

    has = lambda words: any(w in blob for w in words)
    flags = {
        "birthday": has(KEY_BIRTHDAY),
        "weekday": has(KEY_WEEKDAY),
        "holiday_excluded": has(KEY_HOLIDAY_EXCL),
        "perk": has(KEY_PERK),
        "parking": has(KEY_PARKING),
        "hotspring": has(KEY_HOTSPRING),
        "pet": has(KEY_PET),
        "whole_house": has(KEY_WHOLE),
        "no_breakfast": has(KEY_NO_BREAKFAST),
        "breakfast": has(KEY_BREAKFAST) and not has(KEY_NO_BREAKFAST),
        "has_amount": bool(discounts),
    }

    return {
        "weekday_price": weekday_price,
        "discounts": discounts,
        "price_mentions": sorted(set(prices))[:6],
        "channels": channels,
        "flags": flags,
        "period": latest_period(rec["plans"]),
    }


def dedupe_plans(plans):
    """同一類別下偶爾會有一模一樣的重複方案，去掉。"""
    seen, out = set(), []
    for p in plans:
        key = (p["category"], (p.get("text") or "").strip(), p.get("period") or "")
        if key in seen:
            continue
        seen.add(key)
        p["text"] = clean(p.get("text"))
        out.append(p)
    return out


def main():
    blob = jload(os.path.join(RAW, "merged.json"))
    if not blob:
        raise SystemExit("找不到 raw/merged.json，請先跑 enrich.py")
    rows = blob["stays"]

    stat = collections.Counter()
    for r in rows:
        r["plans"] = dedupe_plans(r["plans"])
        r.update(analyse(r))
        stat["有平日雙人房價"] += bool(r["weekday_price"])
        stat["有折抵金額"] += bool(r["discounts"])
        stat["提及生日券"] += r["flags"]["birthday"]
        stat["有優惠期限"] += bool(r["period"])

    print("[抽取] %s" % dict(stat), flush=True)
    blob["stays"] = rows
    jdump(blob, os.path.join(RAW, "merged.json"))
    print("[完成] 已更新 raw/merged.json")


if __name__ == "__main__":
    main()
