# -*- coding: utf-8 -*-
"""合併各優惠類別，並補上座標／地址／鄉鎮／價格等資料。

座標來源優先序（每筆都記 geo_source 供稽核）：
  1. opendata  — 交通部觀光署「旅館民宿」開放資料（dataset 7780，每日更新，含經緯度）
  2. geocode   — 抓官網詳情頁取地址，再用 OSM Nominatim 地理編碼（結果永久快取）
  3. township  — 該鄉鎮市區的質心（由開放資料同鄉鎮旅宿平均而得），標為約略位置
沒有任何一筆會因為找不到座標而從地圖上消失。
"""
import os, re, io, json, time, zipfile, collections
import requests
from bs4 import BeautifulSoup
from config import (CATEGORIES, OPENDATA_HOTEL_ZIP, UA, RAW, CACHE, DETAIL_URL,
                    jload, jdump, norm_text, norm_name, norm_phones, city_norm)

OD_PATH = os.path.join(CACHE, "opendata_hotel.json")
GEOCACHE = os.path.join(CACHE, "geocache.json")
DETAILCACHE = os.path.join(CACHE, "detailcache.json")
NOMINATIM = "https://nominatim.openstreetmap.org/search"

HOTEL_CLASS = {1: "國際觀光旅館", 2: "一般觀光旅館", 3: "一般旅館", 4: "民宿"}


# ---------------------------------------------------------------- 開放資料

def load_opendata(force=False):
    if force or not os.path.exists(OD_PATH):
        print("[開放資料] 下載 Hotel-json.zip ...", flush=True)
        r = requests.get(OPENDATA_HOTEL_ZIP, headers={"User-Agent": UA}, timeout=300)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
        text = z.read("HotelList.json").decode("utf-8-sig")
        with open(OD_PATH, "w", encoding="utf-8") as f:
            f.write(text)
    with open(OD_PATH, encoding="utf-8") as f:
        d = json.load(f)
    print("[開放資料] %d 筆，更新於 %s" % (len(d["Hotels"]), d.get("UpdateTime")), flush=True)
    return d


def build_index(hotels):
    by_phone = collections.defaultdict(list)
    by_name = collections.defaultdict(list)
    by_name_loose = collections.defaultdict(list)
    towns = collections.defaultdict(list)
    for h in hotels:
        pa = h.get("PostalAddress") or {}
        city = city_norm(pa.get("City") or "")
        town = pa.get("Town") or ""
        for t in (h.get("Telephones") or []):
            for p in norm_phones(t.get("Tel")):
                by_phone[p].append(h)
        by_name[(norm_text(h.get("HotelName")), city)].append(h)
        by_name_loose[(norm_name(h.get("HotelName")), city)].append(h)
        lat, lon = h.get("PositionLat"), h.get("PositionLon")
        if city and town and lat and lon:
            towns[(city, town)].append((lat, lon))
    centroids = {}
    for (c, t), v in towns.items():
        centroids[c + "|" + t] = (sum(x for x, _ in v) / len(v), sum(y for _, y in v) / len(v))
    return by_phone, by_name, by_name_loose, centroids


def pick(cands, row):
    """同一支電話可能對到連鎖的多家分館，用名稱再篩一次。"""
    if not cands:
        return None
    if len(cands) == 1:
        return cands[0]
    target = norm_name(row["name"])
    for h in cands:
        if norm_name(h.get("HotelName")) == target:
            return h
    for h in cands:
        other = norm_name(h.get("HotelName"))
        if target and other and (target in other or other in target):
            return h
    return cands[0]


def match(row, by_phone, by_name, by_name_loose):
    for p in norm_phones(row["phone_raw"]):
        h = pick(by_phone.get(p), row)
        if h:
            return h, "phone"
    h = pick(by_name.get((norm_text(row["name"]), row["city"])), row)
    if h:
        return h, "name_exact"
    h = pick(by_name_loose.get((norm_name(row["name"]), row["city"])), row)
    if h:
        return h, "name_norm"
    return None, ""


# ------------------------------------------------- 詳情頁 + 地理編碼（少量）

def fetch_detail(hohi_id, session, cache):
    """未命中開放資料的少數幾筆，才去抓官網詳情頁拿地址。結果永久快取。"""
    if hohi_id in cache:
        return cache[hohi_id]
    info = {"address": "", "website": ""}
    try:
        r = session.get(DETAIL_URL.format(hohi_id), timeout=120)
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
        for th in soup.find_all("th"):
            label = th.get_text(strip=True)
            td = th.find_next("td")
            if not td:
                continue
            if label.startswith("地址"):
                info["address"] = td.get_text(" ", strip=True)
            elif "網址" in label or "官網" in label:
                a = td.find("a")
                info["website"] = (a.get("href") if a else td.get_text(strip=True)) or ""
    except Exception as e:
        print("  詳情頁 %s 失敗：%s" % (hohi_id, e), flush=True)
    cache[hohi_id] = info
    time.sleep(1)                      # 官網很慢，別壓它
    return info


def clean_address(addr):
    """官網地址常有重複的縣市、里名、樓層與括號附註，Nominatim 吃不下。
    回傳由完整到精簡的多個候選，依序嘗試。"""
    if not addr:
        return []
    a = re.sub(r"\s+", "", addr)
    a = re.sub(r"^\d{3,5}", "", a)                     # 開頭郵遞區號
    m = re.match(r"(\S{2,3}[縣市]\S{1,4}[鄉鎮市區])", a)
    if m:                                              # 去掉重複的「縣市＋鄉鎮」前綴
        head = m.group(1)
        while a[len(head):].startswith(head):
            a = head + a[len(head) * 2:]
    a = re.sub(r"[（(][^）)]*[）)]", "", a)              # 括號附註
    # 里名（只刪緊接在鄉鎮市區之後的，避免誤傷「埔里鎮」這類地名）
    a = re.sub(r"(?<=[鄉鎮市區])([^\d\s]{1,3}里)(?=[^\d\s]*[路街道段巷弄號])", "", a)
    cands = []
    m = re.match(r"^(.*?\d+號)", a)                     # 截到門牌號為止
    if m:
        cands.append(m.group(1))
    cands.append(a)
    m = re.match(r"^(\S{2,3}[縣市]\S{1,4}[鄉鎮市區][^0-9]*\d+號)", a)
    if m:
        cands.append(m.group(1))
    out = []
    for c in cands:
        c = c.strip("，,、-")
        if c and c not in out:
            out.append(c)
    return out


def geocode(address, cache, session):
    """OSM Nominatim，遵守 1 req/s。結果（含失敗）都快取，不重複打。
    地址會先清洗成數個候選，由精確到寬鬆逐一嘗試。"""
    if not address:
        return None
    if address in cache and cache[address]:
        return cache[address]
    result = None
    for q in clean_address(address):
        try:
            r = session.get(NOMINATIM, params={"q": q, "format": "json", "limit": 1,
                                               "countrycodes": "tw"}, timeout=60)
            j = r.json()
            if j:
                result = [float(j[0]["lat"]), float(j[0]["lon"])]
        except Exception as e:
            print("  地理編碼失敗 %s：%s" % (q, e), flush=True)
        time.sleep(1.1)
        if result:
            break
    cache[address] = result
    return result


# ---------------------------------------------------------------- 主流程

def merge_categories():
    """以 hohi_id 去重；同一家旅宿可同時擁有多個優惠標籤。"""
    merged, total = {}, 0
    for cat in CATEGORIES:
        blob = jload(os.path.join(RAW, cat["key"] + ".json"))
        if not blob:
            raise SystemExit("找不到 raw/%s.json，請先跑 scrape.py" % cat["key"])
        total += len(blob["rows"])
        for row in blob["rows"]:
            rec = merged.setdefault(row["hohi_id"], {
                "id": row["hohi_id"], "name": row["name"], "phone_raw": row["phone_raw"],
                "city": row["city"], "kind": row["kind"], "categories": [], "plans": [],
            })
            if cat["key"] not in rec["categories"]:
                rec["categories"].append(cat["key"])
            rec["plans"].append({"category": cat["key"], "category_name": cat["name"],
                                 "text": row["plan_raw"], "period": row["period"],
                                 "links": row["links"]})
    print("[合併] %d 筆方案 -> 去重後 %d 家旅宿" % (total, len(merged)), flush=True)
    return list(merged.values())


def main():
    rows = merge_categories()

    od = load_opendata()
    by_phone, by_name, by_name_loose, centroids = build_index(od["Hotels"])

    unmatched = []
    for r in rows:
        h, how = match(r, by_phone, by_name, by_name_loose)
        r["phones"] = norm_phones(r["phone_raw"])
        if h:
            pa = h.get("PostalAddress") or {}
            r["town"] = pa.get("Town") or ""
            r["address"] = (city_norm(pa.get("City") or "") + (pa.get("Town") or "")
                            + (pa.get("StreetAddress") or "")).strip()
            r["zipcode"] = pa.get("ZipCode") or ""
            r["website"] = h.get("WebsiteURL") or ""
            r["booking_urls"] = [u for u in (h.get("ReservationURLs") or []) if u]
            r["stars"] = h.get("HotelStars") or 0
            r["taiwan_host"] = bool(h.get("TaiwanHost"))
            r["classes"] = [HOTEL_CLASS.get(c) for c in (h.get("HotelClasses") or [])
                            if HOTEL_CLASS.get(c)]
            r["price_low"] = h.get("LowestPrice") or 0
            r["price_high"] = h.get("CeilingPrice") or 0
            # ServiceInfo 是逗號串起來的設施清單（含大量空欄位），拆成陣列供前端篩選
            r["services"] = [t.strip() for t in re.split(r"[,、]", h.get("ServiceInfo") or "")
                             if t.strip()]
            r["parking_spaces"] = h.get("ParkingSpaces") or 0
            r["accessible_rooms"] = h.get("AccessibleRooms") or 0
            r["capacity"] = h.get("TotalCapacity") or 0
            r["license"] = h.get("HotelLicenseNumber") or ""
            r["service_status"] = h.get("ServiceStatus")
            lat, lon = h.get("PositionLat"), h.get("PositionLon")
            if lat and lon:
                r["lat"], r["lng"] = round(float(lat), 6), round(float(lon), 6)
                r["geo_source"] = "opendata"
            r["match_method"] = how
        if not r.get("lat"):
            unmatched.append(r)

    print("[比對] 開放資料命中 %d / %d" % (len(rows) - len(unmatched), len(rows)), flush=True)

    if unmatched:
        session = requests.Session()
        session.headers.update({"User-Agent": UA})
        dcache = jload(DETAILCACHE, {}) or {}
        gcache = jload(GEOCACHE, {}) or {}
        print("[補值] %d 筆需要抓詳情頁與地理編碼" % len(unmatched), flush=True)
        for r in unmatched:
            info = fetch_detail(r["id"], session, dcache)
            if not r.get("address"):
                # 詳情頁地址常把「縣市＋鄉鎮」重複一次，顯示前先去重
                a = re.sub(r"\s+", "", info["address"])
                m = re.match(r"(\S{2,3}[縣市]\S{1,4}[鄉鎮市區])", a)
                if m and a[len(m.group(1)):].startswith(m.group(1)):
                    a = a[len(m.group(1)):]
                r["address"] = a
            if not r.get("website"):
                r["website"] = info["website"]
            pos = geocode(info["address"], gcache, session)
            if pos:
                r["lat"], r["lng"] = round(pos[0], 6), round(pos[1], 6)
                r["geo_source"] = "geocode"
            if not r.get("town"):
                m = re.search(r"[縣市](\S{1,3}[鄉鎮市區])", info["address"] or "")
                if m:
                    r["town"] = m.group(1)
        jdump(dcache, DETAILCACHE)
        jdump(gcache, GEOCACHE)

    # 保底：鄉鎮質心 ->（再不行）縣市質心
    per_city = collections.defaultdict(list)
    for key, pos in centroids.items():
        per_city[key.split("|")[0]].append(pos)
    city_centroids = {c: (sum(a for a, _ in v) / len(v), sum(b for _, b in v) / len(v))
                      for c, v in per_city.items()}

    for r in rows:
        if r.get("lat"):
            continue
        pos = centroids.get(r["city"] + "|" + r.get("town", "")) or city_centroids.get(r["city"])
        if pos:
            r["lat"], r["lng"] = round(pos[0], 6), round(pos[1], 6)
            r["geo_source"] = "township"

    stat = collections.Counter(r.get("geo_source", "none") for r in rows)
    match_stat = collections.Counter(r.get("match_method", "none") for r in rows)
    exact = stat["opendata"] + stat["geocode"]
    print("[座標] %s  精確率 %.1f%%" % (dict(stat), exact / len(rows) * 100), flush=True)
    print("[比對方式] %s" % dict(match_stat), flush=True)

    jdump({"stays": rows, "opendata_update": od.get("UpdateTime"),
           "geo_stat": dict(stat), "match_stat": dict(match_stat)},
          os.path.join(RAW, "merged.json"))
    print("[完成] raw/merged.json  %d 家" % len(rows))


if __name__ == "__main__":
    main()
