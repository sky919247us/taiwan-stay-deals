# -*- coding: utf-8 -*-
"""從臺灣旅宿網「優宿專區」抓取各優惠類別的完整名單。

官網的分頁參數是 PNO01（PGA01 會被伺服器忽略），PNUM 可以直接設很大一次抓完。
輸出 raw/<key>.json 與 raw/snapshots/<key>.html。
"""
import re, sys, time, datetime
import requests
from bs4 import BeautifulSoup
from config import (CATEGORIES, LIST_URL, UA, RAW, SNAP, jdump, city_norm)
import os

TIMEOUT = 300


def fetch_category(cat, session):
    data = {
        "TSA050001": cat["uuid"], "TSA051001": "", "PNO01": "1", "PNUM": "3000",
        "PGA01": "", "TSA054": "", "CITY": "", "hohi_kind": "",
        "TSA054005": "", "TSA054008": "",
    }
    last = None
    for attempt in range(1, 4):
        try:
            r = session.post(LIST_URL, data=data, timeout=TIMEOUT)
            r.raise_for_status()
            r.encoding = "utf-8"
            return r.text
        except Exception as e:          # 官網很慢，逾時是常態，重試
            last = e
            print(f"  第 {attempt} 次失敗：{e}", flush=True)
            time.sleep(5 * attempt)
    raise RuntimeError(f"{cat['name']} 抓取失敗：{last}")


def parse(html, cat):
    soup = BeautifulSoup(html, "html.parser")

    # 官網自己顯示的總筆數，拿來對帳
    m = re.search(r"共([\d,]+)筆", html)
    declared = int(m.group(1).replace(",", "")) if m else None

    tb = soup.select_one("#printdraw table tbody")
    if tb is None:
        raise RuntimeError(f"{cat['name']}：找不到結果表格，官網可能改版了")

    rows = []
    for tr in tb.find_all("tr", recursive=False):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 5:
            continue
        ps = tds[0].find_all("p")
        name = ps[0].get_text(strip=True) if ps else ""
        phone = ps[1].get_text(strip=True) if len(ps) > 1 else ""

        bits = [t.strip() for t in tds[1].get_text("|").split("|") if t.strip()]
        city = city_norm(bits[0]) if bits else ""
        kind = bits[1] if len(bits) > 1 else ""

        plan = tds[2].get_text("\n", strip=True)
        period = tds[3].get_text(" ", strip=True)

        hid, links = "", []
        for a in tds[4].find_all("a"):
            href = a.get("href", "")
            if "hohi_id=" in href:
                hid = re.search(r"hohi_id=(\d+)", href).group(1)
            elif href and not href.startswith("javascript"):
                links.append({"label": a.get_text(strip=True), "url": href})

        if not name or not hid:
            continue
        rows.append({"hohi_id": hid, "name": name, "phone_raw": phone, "city": city,
                     "kind": kind, "plan_raw": plan, "period": period, "links": links})

    return rows, declared


def main():
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    stamp = datetime.date.today().isoformat()
    report = {}

    for cat in CATEGORIES:
        print(f"[抓取] {cat['name']} …", flush=True)
        t0 = time.time()
        html = fetch_category(cat, session)
        rows, declared = parse(html, cat)
        print(f"  取得 {len(rows)} 筆（官網宣告 {declared} 筆），耗時 {time.time()-t0:.0f}s", flush=True)

        # 對帳：筆數不符就中止，不要把壞資料往下游送
        if declared is not None and declared != len(rows):
            raise SystemExit(f"筆數對帳失敗：{cat['name']} 官網 {declared} 筆，解析出 {len(rows)} 筆")
        if len(rows) < 50:
            raise SystemExit(f"{cat['name']} 只解析到 {len(rows)} 筆，明顯異常，中止")

        with open(os.path.join(SNAP, f"{cat['key']}.html"), "w", encoding="utf-8") as f:
            f.write(html)
        jdump({"category": cat, "fetched_at": stamp, "count": len(rows), "rows": rows},
              os.path.join(RAW, f"{cat['key']}.json"))
        report[cat["key"]] = len(rows)

    print("[完成]", report)


if __name__ == "__main__":
    main()
