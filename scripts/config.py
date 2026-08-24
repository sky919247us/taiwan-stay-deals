# -*- coding: utf-8 -*-
"""共用設定與工具。"""
import os, re, json, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw")
SNAP = os.path.join(RAW, "snapshots")
CACHE = os.path.join(ROOT, "cache")
DATA = os.path.join(ROOT, "public", "data")
DOWNLOADS = os.path.join(DATA, "downloads")
for d in (RAW, SNAP, CACHE, DATA, DOWNLOADS):
    os.makedirs(d, exist_ok=True)

BASE = "https://www.taiwanstay.net.tw/TSA/web_page/"
LIST_URL = BASE + "TSA060200.jsp"          # 列表檢視，表格結構乾淨
DETAIL_URL = BASE + "TSA020200.jsp?hohi_id={}"
UA = "taiwan-stay-deals/1.0 (personal, non-commercial; data from Taiwan Tourism Administration taiwanstay.net.tw)"

# 本次收錄的優惠類別。要擴充只要在這裡加一行。
CATEGORIES = [
    {"key": "subsidy", "name": "國旅補助優惠方案", "uuid": "e2aca5c6-0ad7-4652-9745-84b1a95e358a"},
    {"key": "budget",  "name": "平價優質旅宿",     "uuid": "fcdc9a15-a471-4362-ac68-8d067ea4d4dd"},
]
# 其餘 7 類（暫不收錄，保留備用）
CATEGORIES_AVAILABLE = {
    "住宿優惠方案": "2f1d07de-9914-4df9-9b6c-42e51a510df6",
    "國旅卡專區": "46de125d-7ffe-45de-8edf-d2c97d14c26b",
    "軍人優惠方案": "59b7b961-3dc8-4153-a434-2b90b0dc04d2",
    "學生住宿優惠方案": "1e598567-7cef-461f-99cb-6fd5aa71eae5",
    "住宿X低碳運具": "a098a86e-6f8b-4469-b21e-8d02a9b1ec0e",
    "臺灣好行優惠套票": "bbdf16b4-8024-415a-a5d6-d2db9dee0460",
    "活動優惠專區": "ed3dcc3b-8a6d-4986-9d12-64aa637e8ac8",
}

OPENDATA_HOTEL_ZIP = "https://media.taiwan.net.tw/XMLReleaseAll_public/v2.0/Zh_tw/Hotel-json.zip"

CITY_ORDER = ["臺北市","新北市","基隆市","桃園市","新竹市","新竹縣","苗栗縣","臺中市","彰化縣",
              "南投縣","雲林縣","嘉義市","嘉義縣","臺南市","高雄市","屏東縣","宜蘭縣","花蓮縣",
              "臺東縣","澎湖縣","金門縣","連江縣"]

ISLAND_CITIES = {"澎湖縣", "金門縣", "連江縣"}   # 離島（補助額度較高）


def jload(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def jdump(obj, path, indent=1):
    """先寫暫存檔再置換，確保中途失敗不會留下半截檔案。

    Windows 上 git、防毒、檔案索引器都可能短暫鎖住目標檔，讓 os.replace
    噴 PermissionError（實際發生過：背景抓取正在寫，同時 git add 在讀）。
    退避重試幾次即可，不該讓整個長時間工作因此中斷。"""
    import time
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent)
    for attempt in range(6):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.4 * (attempt + 1))
    # 真的換不過去就保留 .tmp，資料不會遺失，下次寫入會再試
    raise RuntimeError("無法置換 %s（檔案被鎖住），資料暫存在 %s" % (path, tmp))


def norm_text(s):
    """全半形統一、去空白、小寫。用於名稱比對與關鍵字搜尋。"""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"\s+", "", s).lower()


_SUFFIX = re.compile(r"(民宿|旅宿|旅館|飯店|酒店|villa|hotel|inn|resort|hostel|會館|山莊|旅店)+$", re.I)


def norm_name(s):
    """再去掉常見業別後綴，做較寬鬆的名稱比對。"""
    s = norm_text(s)
    s = re.sub(r"[()（）\-‧·．.,、／/]+", "", s)
    prev = None
    while prev != s:
        prev = s
        s = _SUFFIX.sub("", s)
    return s


_PHONE_RE = re.compile(r"09\d{2}-?\d{6}|0\d{1,2}-?\d{6,8}|\d{7,8}")


def norm_phones(s):
    """官網電話欄常把多組號碼「直接串在一起」（例：095541020008-8882611），
    不能用分隔符切，改用號碼樣式掃描。回傳純數字字串清單。"""
    if not s:
        return []
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\+?886-?", "0", s)
    s = re.sub(r"[()（）\s]+", "", s)
    out = []
    for m in _PHONE_RE.finditer(s):
        d = re.sub(r"\D", "", m.group())
        if len(d) >= 7 and d not in out:
            out.append(d)
    return out


def city_norm(c):
    """台/臺 統一，並補上「台北」這類簡寫。"""
    if not c:
        return ""
    c = c.strip().replace("台", "臺")
    return c
