# 2026 國旅補助旅宿地圖

115 年（2026）國旅平日住宿獎助與平價優質旅宿的參與名單查詢站。
資料每週自動從交通部觀光署臺灣旅宿網抓取，做成**全靜態網站**：一次載入後，所有搜尋都在瀏覽器端完成。

**為什麼做這個**：官方「優宿專區」單次查詢要等 20 秒以上、一頁只顯示 10 筆分 92 頁，
而且只有關鍵字／縣市／業別／價格四個下拉，沒有鄉鎮、沒有地圖、沒有距離、沒有排序。

| | 官方優宿專區 | 本站 |
|---|---|---|
| 查詢速度 | 每次 20 秒以上（打伺服器） | 首次載入約 1 秒，之後每次篩選 < 30ms |
| 一次可見 | 10 筆／92 頁 | 全部，捲動即載入 |
| 地區篩選 | 只到縣市 | 縣市 → 鄉鎮市區 |
| 地圖 | 無（只有外連 Google Maps） | 有：圖釘叢集、地圖範圍篩選、圈選半徑、我附近 |
| 設施條件 | 無 | 43 種（停車場、溫泉、寵物友善、國旅卡、無障礙房…） |
| 房價 | 四個固定級距下拉 | 雙向滑桿＋數字輸入，可任意設上下限 |
| 排序 | 無 | 距離／房價／名稱 |
| 分享查詢 | 無 | 條件寫在網址，可直接分享 |

---

## 搜尋方式

1. **關鍵字全文** — 旅宿名稱、地址、設施、方案內容一起搜
2. **縣市 → 鄉鎮市區** 二層連動
3. **業別** — 觀光旅館／旅館／民宿
4. **優惠類別** — 國旅補助／平價優質（可同時勾選，代表兩者都有）
5. **房價區間** — 雙向滑桿可同時調上下限，也能直接輸入數字；另有 2,000 以下／2,000–5,000／
   5,000–10,000／10,000 以上四組常用區間可一鍵套用，每組都標了家數。
   取值為平日雙人房價，無則取開放資料的最低房價；可選擇是否納入未標價的旅宿。
   滑桿刻度是非線性的（500 元起跳、貴的區間放粗），因為房價中位數 2,760 但最高到 60,000，
   線性刻度會把九成資料擠在最左邊
6. **地圖範圍篩選** — 拖曳地圖，清單即時只剩視野內的結果
7. **圈選半徑** — 在地圖上點一個中心點，設定 3／5／10／30 km
8. **我附近** — 瀏覽器定位後依距離排序
9. **優惠條件** — 生日券、有標折抵金額、含早餐、可包棟、好客民宿…
10. **設施服務** — 來自觀光署開放資料的 43 種設施
11. **排序** — 距離最近／房價低到高／房價高到低／名稱
12. **收藏** — 存在瀏覽器，可切換「只看收藏」

外加：深淺色主題、手機清單／地圖切換、Excel / CSV / JSON 下載、補助規則說明。

---

## 資料從哪來

| 來源 | 提供什麼 |
|---|---|
| [臺灣旅宿網 優宿專區](https://www.taiwanstay.net.tw/TSA/web_page/TSA060100.jsp) | 參與名單、方案內容、優惠期限 |
| [觀光署「旅館民宿」開放資料](https://data.gov.tw/dataset/7780)（每日更新） | 地址、經緯度、鄉鎮、房價區間、設施、星級、好客民宿 |
| [OSM Nominatim](https://nominatim.openstreetmap.org/) | 少數未收錄於開放資料者的地理編碼 |

**座標怎麼補**（官網完全沒有經緯度）：

1. 用電話號碼比對開放資料 → 命中 1,728 家
2. 名稱＋縣市完全相同 → 再命中 65 家
3. 剩下的抓官網詳情頁取地址，再送 Nominatim 地理編碼
4. 都失敗就用該鄉鎮的質心，並在卡片上標「位置約略」

目前精確定位率 **99.8%**（1,793 / 1,796）。沒有任何一筆會因為找不到座標而從地圖上消失。

---

## 本機執行

```bash
pip install -r requirements.txt
python scripts/scrape.py     # 抓官網名單（約 2 分鐘，官網很慢）
python scripts/enrich.py     # 比對開放資料、補座標
python scripts/extract.py    # 從方案文字抽出可篩選欄位
python scripts/build.py      # 產出 public/data/*.json 與下載檔
python scripts/verify.py     # 驗收，不過就結束於非零狀態
```

預覽網站（任何靜態伺服器都行）：

```bash
python -m http.server 8787 --directory public
```

---

## 部署到 Cloudflare Pages（免費）

1. 把這個資料夾推到 GitHub（公開 repo，Actions 才完全免費）。
2. Cloudflare Dashboard → **Workers & Pages** → **Create** → **Pages** → **Connect to Git**，選這個 repo。
3. 建置設定：
   - **Framework preset**：None
   - **Build command**：**留空**
   - **Build output directory**：`public`
4. Save and Deploy。之後每次 push 自動重新部署，PR 會有預覽網址。
5. （選用）Custom domains 綁自己的網域，SSL 自動配好。

`public/_headers` 已設定好快取策略：vendor 檔一年、資料檔 1 小時、其他 10 分鐘。

### 每週自動更新

`.github/workflows/update.yml` 每週一 02:00 UTC（台灣時間週一上午 10 點）跑一次，
也可以在 Actions 頁面手動觸發（**Run workflow**）。流程是
抓取 → 補值 → 抽取 → 產出 → 驗收 → **有異動才 commit**，push 後 Cloudflare 自動重新部署。

安全機制：

- 抓取階段會和官網顯示的「共 N 筆」對帳，數字不符直接中止，不會把壞資料往下游送。
- `verify.py` 檢查筆數、必要欄位、座標精確率（< 95% 就失敗）、座標是否落在台灣範圍內。
- 所有 JSON 都是先寫 `.tmp` 再置換，中途失敗不會留下半截檔案。
- 沒有異動就不 commit，不會產生無意義的部署。

### 免費額度

| 服務 | 實際用量 | 免費上限 |
|---|---|---|
| GitHub Actions（公開 repo） | 每月約 4 次、每次 < 10 分鐘 | 無限 |
| Cloudflare Pages 建置 | 每月約 4 次 | 500 次／月 |
| Cloudflare 流量 | 每次瀏覽約 300KB | 無上限 |
| OSM 圖磚 | 依瀏覽量 | 使用政策允許低流量站 |
| Nominatim | 首次數十次，之後全走 `cache/geocache.json` | 1 req/s |

**總成本 0 元**（自訂網域另計）。

---

## 專案結構

```
public/            ← Cloudflare Pages 的輸出目錄
  index.html  app.js  style.css  _headers  robots.txt
  vendor/          Leaflet 與 markercluster（自帶，不依賴 CDN）
  data/            stays.json  meta.json  downloads/*.xlsx|csv
scripts/
  config.py        共用設定、名稱／電話正規化
  scrape.py        抓官網（POST TSA060200.jsp，分頁參數是 PNO01）
  enrich.py        合併類別、比對開放資料、補座標
  extract.py       從方案文字抽出可篩選欄位
  build.py         產出前端資料與下載檔、寫 CHANGELOG-data.md
  verify.py        自動驗收
raw/               各類別原始 JSON（納入版控，用來對帳與 diff）
cache/             geocache.json / detailcache.json（納入版控，避免重跑地理編碼）
```

要擴充其他優惠類別（國旅卡專區、軍人優惠、學生住宿…），
只要在 `scripts/config.py` 的 `CATEGORIES` 加一行即可，UUID 已列在 `CATEGORIES_AVAILABLE`。

---

## 免責

本站為非官方整理。優惠內容、參與資格與名單以**官方公告及旅宿業者說明為準**；
名單會滾動增修，訂房前請再確認。官方諮詢：交通部觀光署 (02) 2349-1500。
