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
| 房價 | 四個固定級距下拉，且只有灌水的定價 | 優惠價與定價分開呈現；雙向滑桿＋數字輸入 |
| 排序 | 無 | 距離／房價／名稱 |
| 分享查詢 | 無 | 條件寫在網址，可直接分享 |

---

## 搜尋方式

1. **關鍵字全文** — 旅宿名稱、地址、設施、方案內容一起搜
2. **縣市 → 鄉鎮市區** 二層連動
3. **業別** — 觀光旅館／旅館／民宿
4. **優惠類別** — 國旅補助／平價優質（可同時勾選，代表兩者都有）
5. **平日雙人房優惠價** — 雙向滑桿可同時調上下限，也能直接輸入數字；另有
   1,600 以下／1,600–2,200／2,200–3,000／3,000 以上四組常用區間，每組都標了家數。
   只採用業者為本活動自報的優惠價（966 家，798–4,020 元），可選擇是否納入未標價的 830 家
6. **地圖範圍篩選** — 拖曳地圖，清單即時只剩視野內的結果
7. **圈選半徑** — 在地圖上點一個中心點，設定 3／5／10／30 km
8. **我附近** — 瀏覽器定位後依距離排序
9. **Google 評分** — 評分下限滑桿（刻度在 4.0–5.0 之間切細，因為評分中位數是 4.7）
   ＋評論數門檻（10／50／100／300／1000 則）＋四組常用評分一鍵套用；
   可選擇是否納入 Google 上查不到評分的旅宿
10. **優惠條件** — 生日券、有標折抵金額、含早餐、可包棟、好客民宿…
11. **設施服務** — 來自觀光署開放資料的 43 種設施
12. **排序** — 距離最近／房價／Google 評分／評論數最多／名稱
13. **收藏** — 存在瀏覽器，可切換「只看收藏」

外加：深淺色主題、Excel / CSV / JSON 下載、補助規則說明。

### 手機／平板

- **≥760px**（平板橫放、桌機）：左清單右地圖同時顯示
- **<760px**（手機）：底部分頁切換「清單／地圖」，篩選列只留搜尋＋縣市＋我附近，其餘收在「更多條件」
- **≤360px**：「我附近」只留圖示
- 手機橫放（高度 ≤480px）另有一組壓縮版面
- 用 `100dvh` 避免被瀏覽器網址列切掉，瀏海與 home 指示條用 `env(safe-area-inset-*)` 避開
- 觸控裝置的按鈕、籌碼、滑桿把手都放大到約 44px；輸入框 16px，iOS 才不會一點就放大整頁
- 詳情在手機上是從底部升起的 bottom sheet
- 可加到主畫面（`site.webmanifest`，含 maskable 圖示）

---

## 價格：四種可信來源 ＋ 兩種僅供參考

官方資料裡的「定價」根本不能用。拿 965 家同時有兩種價格的旅宿實測，
**定價中位數是實際優惠價的 1.9 倍**，前 10% 超過 4 倍，最誇張 12.5 倍
（花蓮海悅酒店：定價 25,000／實際 2,000）。有業者直說是「還沒收到正式公文，
先隨便填一個」。所以本站自己把真實價格湊出來，並嚴格分級：

**可信房價**（參與篩選與排序，優先序由高到低）

| 來源 | 怎麼來的 | 家數 |
|---|---|---|
| 人工查核 | `overrides/prices.csv`，人查了填進去 | 依實際填寫 |
| 業者自報 | 「平價優質旅宿」活動的欄位 | 966 |
| 方案說明 | 業者順手寫在方案文字裡，LLM 抽出並附原文佐證 | 22 |
| 業者官網 | 抓官網 → LLM 抽價（純 HTTP ＋ 無頭瀏覽器） | 81 |

只收確認為**平日價**的。實測踩過的坑：飯店官網的「NT$13,000+10%」是牌價、
「加999元升等」是加價、「休息3小時780元」是汽旅時段、「折抵後每晚4360」
是補助後淨價 —— 這些一律不採。

**僅供參考**（預設不參與篩選，卡片上用灰色徽章區隔）

| 來源 | 說明 |
|---|---|
| 訂房平台參考價 | SerpApi 查 Google Hotels，固定用補助期間內的一個平日日期，取各平台最低報價 |
| 官網定價 | 開放資料的牌價，只在詳情頁並陳、加刪除線 |

訂房平台的價格**多數不能折抵補助** —— 26 家業者在方案裡明講「線上訂房平台
不能折抵」，官方規則也是限直接訂房或核可平台。所以它只是比價參考，
篩選要另外勾「含平台參考價」才會納入。

### 訂房平台的即時參考價

詳情頁有一顆「查 X/X（X）即時房價」按鈕，會用**補助期間內的一個平日日期**
開啟 Google 飯店搜尋，顯示各訂房平台當下的報價。

刻意**不把那個價格抓下來存檔**，三個理由：

1. 它綁特定日期，同一晚各平台差到 38%（煙波蘇澳館 Traveloka $3,646 vs 易遊網 $5,051），
   存下來隔天就過期
2. 那些平台多半**不能折抵補助** —— 26 家業者在方案內容裡明講「線上訂房平台不能折抵」，
   官方規則也是限直接訂房或核可平台
3. 按鈕只是一條超連結，由訪客自己的瀏覽器去問 Google，
   **不消耗本專案任何 API 額度**，訪客再多都是 0 成本

因此該按鈕旁明確標註「比價參考，不是本站的補助價」。

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

### 每週更新：在本機跑

```bash
python scripts/weekly.py                # 完整跑一輪，驗收通過就自動 commit & push
python scripts/weekly.py --no-push      # 只跑不推，先看結果
python scripts/weekly.py --quick        # 只更新名單，跳過所有抽價階段
python scripts/weekly.py --with-render  # 額外跑無頭瀏覽器（很慢、收穫少）
```

需要的金鑰都放在 `cache/`（已 gitignore）：`google_api_key.txt`、
`openrouter_key.txt`、`serpapi_key.txt`。缺哪一把，對應的階段會自己跳過，
不影響其餘流程。

流程是抓取 → 補座標 → 抽欄位 → Google 評分 → 三種抽價 → 渲染 → 產出 → 驗收 →
有異動才 commit → push，Cloudflare 收到 push 自動部署。

**為什麼不放 GitHub Actions**：評分與抽價需要 Google 與 OpenRouter 金鑰，
還要 Chromium 渲染 JS 網站。放本機就不用把金鑰交給雲端，也少幾種失敗方式。
`weekly.py` 開頭會先 `git fetch` 並在必要時 rebase，避免和遠端打架。

`.github/workflows/update.yml` 保留為**手動觸發的備援**（排程已關閉）：
它只跑得動抓取與建置，不會補評分與價格。

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
  favicon.ico  icon.svg  apple-touch-icon.png  icon-192/512.png  site.webmanifest
  vendor/          Leaflet 與 markercluster（自帶，不依賴 CDN）
  data/            stays.json  meta.json  downloads/*.xlsx|csv
scripts/
  config.py        共用設定、名稱／電話正規化
  make_icons.py    產生 favicon.ico／PNG／SVG／webmanifest（改圖示時才要跑）
  weekly.py        每週更新的總指揮：跑完整條管線、驗收、commit、push
  places.py        Google 評分與座標修正（Places API）
  planprice.py     從方案文字抽價（LLM）
  webprice.py      抓業者官網抽價（純 HTTP ＋ LLM）
  webprice_js.py   無頭瀏覽器渲染抽價（投報率低，預設不跑）
  otaprice.py      訂房平台參考價（SerpApi Google Hotels）
  manual.py        產生人工查核清單 overrides/prices.csv 與 pending.json
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

## 人工查核台

SerpApi 與各種抽價都補不到的旅宿（多半是沒上任何訂房平台的小民宿），
用 `overrides/entry.html` 手動補。它需要用本機伺服器開啟（要 fetch
`pending.json`）：

```bash
python -m http.server 8788 --directory overrides
# 然後開 http://localhost:8788/entry.html
```

介面是左右分割：左邊一次一家＋價格輸入，右邊即時預覽。快捷鍵
<kbd>G</kbd> Google 查價、<kbd>M</kbd> 地圖、<kbd>W</kbd> 官網、
<kbd>+</kbd><kbd>−</kbd> 縮放、<kbd>Enter</kbd> 存檔下一家、
<kbd>Esc</kbd> 跳過、<kbd>Ctrl+Z</kbd> 復原。進度存在 localStorage，
關掉再開會接續，最後匯出 CSV 貼進 `overrides/prices.csv`。

**一個做不到的事要先說**：Google 搜尋與地圖都送 `X-Frame-Options: SAMEORIGIN`，
瀏覽器強制禁止嵌入 iframe，沒有繞法。所以 Google 改開在一個**固定名稱的側邊
視窗**，換下一家時替換同一個視窗的內容（不會越開越多），而且那個視窗的縮放
比例瀏覽器會依網域記住，設一次就好。右邊的 iframe 則用來內嵌**業者官網**
（545 家裡有 156 家有官網，多數沒擋 iframe）。

## 贊助

頁尾與「下載名單」面板各有一個 Ko-fi 文字連結。

**刻意沒有用 Ko-fi 官方的 floating-chat 浮動視窗**，理由有三個：
一是那顆按鈕固定在右下角，會蓋住手機版底部的「清單／地圖」切換鈕；
二是它要從 `storage.ko-fi.com` 載入外部 script，本站目前所有資源都是自帶的
（Leaflet 也是 vendor 進來的），加一個第三方 script 會帶進追蹤與額外的載入時間；
三是使用者要的是「不起眼」，浮動按鈕正好相反。

要改成浮動視窗的話，把 `index.html` 頁尾前面加上 Ko-fi 給的兩行 script 即可。

## 免責

本站為非官方整理。優惠內容、參與資格與名單以**官方公告及旅宿業者說明為準**；
名單會滾動增修，訂房前請再確認。官方諮詢：交通部觀光署 (02) 2349-1500。
