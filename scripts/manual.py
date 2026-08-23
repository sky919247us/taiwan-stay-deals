# -*- coding: utf-8 -*-
"""產生／更新人工查核價格的覆寫檔 overrides/prices.csv。

用途：有些旅宿既沒有為活動自報優惠價、官網也抓不到價格（純 FB 粉專、
JS 動態網站、或根本沒有網站）。這種只能靠人去查一下再填進來。

人工查核想去哪裡查都可以 —— Google 地圖、訂房網、打電話問 —— 那是人自己
上網看資料，跟程式大量自動抓取是兩回事。這個檔就是把查到的結果收進管線。

每一列都附好 Google 地圖搜尋連結，點下去就是那家店，看到平日雙人房價就填回來。

欄位：
  hohi_id          旅宿編號（別動）
  旅宿名稱          （別動，方便你辨認）
  縣市鄉鎮          （別動）
  平日雙人房價       ← 填這裡，只填數字，例如 1880
  來源             ← 填你在哪看到的，例如 Google地圖 / 官網 / 電話詢問
  查核日期          ← 例如 2026-08-24
  備註             ← 選填
  google_maps      （別動，點了就能查）

填好存檔，跑 build.py 就會併進網站，並在卡片上標「人工查核」。
"""
import os, csv, urllib.parse
from config import ROOT, RAW, CACHE, jload

OVERRIDE_DIR = os.path.join(ROOT, "overrides")
OVERRIDE_CSV = os.path.join(OVERRIDE_DIR, "prices.csv")
COLS = ["hohi_id", "旅宿名稱", "縣市鄉鎮", "平日雙人房價", "來源", "查核日期", "備註", "google_maps"]


def load_overrides():
    """回傳 {hohi_id: {price, source, date, note}}，只收填了有效數字的列。"""
    out = {}
    if not os.path.exists(OVERRIDE_CSV):
        return out
    with open(OVERRIDE_CSV, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            raw = (row.get("平日雙人房價") or "").strip().replace(",", "")
            if not raw.isdigit():
                continue
            p = int(raw)
            if not (300 <= p <= 60000):
                continue
            out[row["hohi_id"].strip()] = {
                "price": p,
                "source": (row.get("來源") or "").strip(),
                "date": (row.get("查核日期") or "").strip(),
                "note": (row.get("備註") or "").strip(),
            }
    return out


def main():
    blob = jload(os.path.join(RAW, "merged.json"))
    if not blob:
        raise SystemExit("找不到 raw/merged.json，請先跑 enrich.py")
    web = jload(os.path.join(CACHE, "webprice.json"), {}) or {}
    existing = {}
    if os.path.exists(OVERRIDE_CSV):
        with open(OVERRIDE_CSV, encoding="utf-8-sig", newline="") as f:
            existing = {r["hohi_id"]: r for r in csv.DictReader(f)}

    todo = []
    for s in blob["stays"]:
        if s.get("weekday_price"):
            continue                                   # 業者已為活動自報，不需人工
        if (web.get(s["id"]) or {}).get("price"):
            continue                                   # 官網已抓到
        q = "%s %s" % (s["name"], s.get("address") or s.get("city", ""))
        todo.append({
            "hohi_id": s["id"],
            "旅宿名稱": s["name"],
            "縣市鄉鎮": (s.get("city") or "") + (s.get("town") or ""),
            "平日雙人房價": "",
            "來源": "",
            "查核日期": "",
            "備註": "",
            "google_maps": "https://www.google.com/maps/search/?api=1&query="
                           + urllib.parse.quote(q),
        })

    # 保留已經填過的內容，不要被重新產生洗掉
    kept = 0
    for row in todo:
        old = existing.get(row["hohi_id"])
        if old and (old.get("平日雙人房價") or "").strip():
            for k in ("平日雙人房價", "來源", "查核日期", "備註"):
                row[k] = old.get(k, "")
            kept += 1

    os.makedirs(OVERRIDE_DIR, exist_ok=True)
    with open(OVERRIDE_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(todo)

    filled = len(load_overrides())
    print("[人工覆寫] 仍缺價格 %d 家，已寫入 %s" % (len(todo), OVERRIDE_CSV))
    print("[人工覆寫] 其中已填好 %d 家（保留了先前填的 %d 筆）" % (filled, kept))


if __name__ == "__main__":
    main()
