# -*- coding: utf-8 -*-
"""輸出後的自動驗收。任何一項不過就以非零狀態結束，讓 CI 紅燈、不要 commit 壞資料。"""
import os, sys, json, collections
from config import RAW, DATA, CATEGORIES, jload

FAIL = []


def main():
    stays_blob = jload(os.path.join(DATA, "stays.json"))
    meta = jload(os.path.join(DATA, "meta.json"))
    if not stays_blob or not meta:
        print("[驗收] 找不到輸出檔"); sys.exit(1)
    stays = stays_blob["stays"]

    # 1. 筆數對帳：每個類別的旅宿家數，要等於原始檔去重後的家數
    for cat in CATEGORIES:
        raw = jload(os.path.join(RAW, cat["key"] + ".json"))
        if not raw:
            FAIL.append("缺少 raw/%s.json" % cat["key"]); continue
        raw_ids = {r["hohi_id"] for r in raw["rows"]}
        out_ids = {s["id"] for s in stays if cat["key"] in s.get("categories", [])}
        if raw_ids != out_ids:
            FAIL.append("%s 家數不符：原始 %d 家，輸出 %d 家" %
                        (cat["name"], len(raw_ids), len(out_ids)))
        else:
            print("[OK] %s %d 家（原始 %d 筆方案）" % (cat["name"], len(out_ids), raw["count"]))

    # 2. 規模：資料量突然掉一半通常代表官網改版或抓取失敗
    if len(stays) < 1000:
        FAIL.append("總筆數只有 %d，明顯異常" % len(stays))

    # 3. 必要欄位
    missing = [s["id"] for s in stays if not s.get("name") or not s.get("city")
               or not s.get("lat") or not s.get("lng")]
    if missing:
        FAIL.append("有 %d 筆缺少名稱／縣市／座標，例如 %s" % (len(missing), missing[:5]))

    # 4. 座標品質
    geo = collections.Counter(s.get("geo_source") for s in stays)
    # google 是用 Places API 比中後採信的座標，比開放資料更準，一樣算精確
    exact = geo["opendata"] + geo["geocode"] + geo["google"]
    rate = exact / len(stays) * 100
    print("[座標] 精確 %d（開放資料 %d／Google %d／地理編碼 %d）／約略 %d，精確率 %.1f%%"
          % (exact, geo["opendata"], geo["google"], geo["geocode"], geo["township"], rate))
    if rate < 95:
        FAIL.append("座標精確率 %.1f%% 低於 95%%" % rate)

    # 5. 座標要落在台灣範圍內
    out_of_range = [s["id"] for s in stays
                    if not (21.5 <= s["lat"] <= 26.5 and 118.0 <= s["lng"] <= 122.5)]
    if out_of_range:
        FAIL.append("有 %d 筆座標落在台灣範圍外：%s" % (len(out_of_range), out_of_range[:5]))

    # 6. meta 與實際資料一致
    if meta["total"] != len(stays):
        FAIL.append("meta.total(%d) 與實際筆數(%d) 不符" % (meta["total"], len(stays)))
    if not meta.get("cities") or not meta.get("services"):
        FAIL.append("meta 缺少縣市或設施清單")

    # 7. 下載檔存在且不是空的
    for f in ("downloads/taiwan-stay-deals.csv", "downloads/taiwan-stay-deals.xlsx"):
        p = os.path.join(DATA, f)
        if not os.path.exists(p) or os.path.getsize(p) < 10000:
            FAIL.append("下載檔異常：%s" % f)

    if FAIL:
        print("\n[驗收失敗]")
        for m in FAIL:
            print("  - " + m)
        sys.exit(1)
    print("\n[驗收通過] %d 家旅宿、%d 個縣市、%d 種設施條件" %
          (len(stays), len(meta["cities"]), len(meta["services"])))


if __name__ == "__main__":
    main()
