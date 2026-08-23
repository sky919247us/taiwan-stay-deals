/* 2026 國旅補助旅宿地圖
   資料一次載入後全部在瀏覽器端查詢，不再打任何後端。 */
'use strict';

var DATA = [];            // 全部旅宿
var META = null;
var VIEW = [];            // 目前篩選＋排序後的結果
var MARKERS = {};         // id -> L.Marker（用到才建）
var map = null, cluster = null, radiusCircle = null, meMarker = null;
var rendered = 0, CHUNK = 60;
var pickingRadius = false;

var CAT_NAME = { subsidy: '國旅補助', budget: '平價優質' };
var GEO_LABEL = { opendata: '', geocode: '', township: '位置為鄉鎮約略值' };

function svc(s, name) { return has(s.services, name); }

var FLAG_DEFS = [
  { key: 'birthday',   label: '生日券',   test: function (s) { return has(s.flags, 'birthday'); } },
  { key: 'has_amount', label: '有標折抵金額', test: function (s) { return has(s.flags, 'has_amount'); } },
  { key: 'breakfast',  label: '含早餐',   test: function (s) { return has(s.flags, 'breakfast'); } },
  { key: 'whole',      label: '可包棟',   test: function (s) { return has(s.flags, 'whole_house'); } },
  { key: 'parking',    label: '有停車',   test: function (s) { return has(s.flags, 'parking') || (s.parking_spaces > 0) || svc(s, '停車場'); } },
  { key: 'hotspring',  label: '溫泉',     test: function (s) { return has(s.flags, 'hotspring') || svc(s, '溫泉設施'); } },
  { key: 'pet',        label: '寵物友善', test: function (s) { return has(s.flags, 'pet') || svc(s, '寵物友善旅宿'); } },
  { key: 'host',       label: '好客民宿', test: function (s) { return !!s.taiwan_host; } },
  { key: 'card',       label: '國旅卡',   test: function (s) { return svc(s, '國民旅遊卡'); } },
  { key: 'access',     label: '無障礙房', test: function (s) { return (s.accessible_rooms > 0) || svc(s, '無障礙客房'); } },
  { key: 'web',        label: '有官網',   test: function (s) { return !!s.website; } },
  { key: 'exact',      label: '精確座標', test: function (s) { return s.geo_source !== 'township'; } }
];

// 設施籌碼只列出在本站資料中夠常見的項目，太罕見的挑了也沒東西看
var SERVICE_MIN = 15, SERVICE_MAX = 18;

var S = {
  q: '', city: '', town: '', cats: [], kinds: [], flags: [], services: [],
  priceMax: 6000, inclUnknown: true, sort: 'default', onlyFav: false,
  near: null,        // { lat, lng, km, label }
  bounds: false
};

var $ = function (id) { return document.getElementById(id); };
function has(arr, v) { return !!arr && arr.indexOf(v) >= 0; }
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  });
}
function norm(s) {
  return String(s || '').normalize('NFKC').toLowerCase().replace(/\s+/g, '');
}
function dist(a, b, c, d) {                       // 兩點距離（公里）
  var R = 6371, p = Math.PI / 180;
  var x = (c - a) * p, y = (d - b) * p;
  var h = Math.sin(x / 2) * Math.sin(x / 2) +
          Math.cos(a * p) * Math.cos(c * p) * Math.sin(y / 2) * Math.sin(y / 2);
  return 2 * R * Math.asin(Math.sqrt(h));
}

/* ------------------------------------------------------------ 收藏 */

var FAV = new Set(JSON.parse(localStorage.getItem('fav') || '[]'));
function toggleFav(id) {
  if (FAV.has(id)) { FAV.delete(id); } else { FAV.add(id); }
  localStorage.setItem('fav', JSON.stringify(Array.from(FAV)));
  $('favCount').textContent = FAV.size ? '(' + FAV.size + ')' : '';
}

/* ------------------------------------------------------------ 載入 */

Promise.all([
  fetch('data/stays.json').then(function (r) { return r.json(); }),
  fetch('data/meta.json').then(function (r) { return r.json(); })
]).then(function (res) {
  DATA = res[0].stays;
  META = res[1];
  DATA.forEach(function (s) {
    s.flags = s.flags || [];
    s.categories = s.categories || [];
    s.plans = s.plans || [];
    s._p = s.weekday_price || s.price_low || 0;        // 排序與篩選用的房價
    s.services = s.services || [];
    s._s = norm([s.name, s.address, s.city, s.town, s.license, s.services.join(' '),
                 s.plans.map(function (p) { return p.text; }).join(' ')].join(' '));
  });
  boot();
}).catch(function (e) {
  $('list').innerHTML = '<p class="empty">資料載入失敗：' + esc(e.message) + '</p>';
});

function boot() {
  buildFilters();
  readURL();
  syncControls();
  bindEvents();

  var d = META.updated_at ? META.updated_at.slice(0, 10) : '';
  $('metaLine').textContent = META.total + ' 家旅宿 ・ 資料更新 ' + d;
  $('footMeta').textContent = '資料擷取時間 ' + esc(META.updated_at) +
    '；開放資料版本 ' + esc(META.opendata_update || '—') + '。';
  var g = META.geo_stat || {};
  var exact = (g.opendata || 0) + (g.geocode || 0);
  $('geoNote').textContent = '座標精確定位 ' + exact + ' 家（' +
    (exact / META.total * 100).toFixed(1) + '%），其餘 ' + (g.township || 0) +
    ' 家以鄉鎮約略位置標示。';

  if (META.change && META.change.added && META.change.added.length) {
    $('metaLine').textContent += ' ・ 本次新增 ' + META.change.added.length + ' 家';
  }
  $('favCount').textContent = FAV.size ? '(' + FAV.size + ')' : '';

  document.body.classList.add('view-list');
  // 進階條件預設收起來，先讓使用者看到結果
  if (S.flags.length || S.services.length || S.priceMax < 6000) {
    $('btnFilters').click();
  }
  apply();
  // 地圖容器有寬度才初始化：桌機一開始就看得到，手機要等切到地圖分頁
  if ($('map').clientWidth > 0) { initMap(); }
}

/* ------------------------------------------------------------ 篩選器 UI */

function buildFilters() {
  var city = $('city');
  META.cities.forEach(function (c) {
    var o = document.createElement('option');
    o.value = c.name;
    o.textContent = c.name + '（' + c.count + '）';
    city.appendChild(o);
  });

  chips($('catChips'), META.categories.map(function (c) {
    return { key: c.key, label: c.name.replace('優惠方案', ''), n: c.count };
  }), 'cats');

  var kinds = Object.keys(META.kinds).map(function (k) {
    return { key: k, label: k, n: META.kinds[k] };
  }).sort(function (a, b) { return b.n - a.n; });
  chips($('kindChips'), kinds, 'kinds');

  chips($('flagChips'), FLAG_DEFS.map(function (f) {
    return { key: f.key, label: f.label, n: DATA.filter(f.test).length };
  }).filter(function (f) { return f.n > 0; }), 'flags');

  chips($('serviceChips'), (META.services || [])
    .filter(function (x) { return x.count >= SERVICE_MIN; })
    .slice(0, SERVICE_MAX)
    .map(function (x) { return { key: x.name, label: x.name, n: x.count }; }), 'services');
}

function chips(box, items, field) {
  box.innerHTML = '';
  items.forEach(function (it) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'chip';
    b.setAttribute('aria-pressed', 'false');
    b.dataset.key = it.key;
    b.innerHTML = esc(it.label) + (it.n != null ? '<span class="n">' + it.n + '</span>' : '');
    b.addEventListener('click', function () {
      var i = S[field].indexOf(it.key);
      if (i >= 0) { S[field].splice(i, 1); } else { S[field].push(it.key); }
      b.setAttribute('aria-pressed', i >= 0 ? 'false' : 'true');
      apply();
    });
    box.appendChild(b);
  });
}

function fillTowns() {
  var sel = $('town');
  var c = META.cities.filter(function (x) { return x.name === S.city; })[0];
  sel.innerHTML = '<option value="">全部鄉鎮</option>';
  sel.disabled = !c;
  if (!c) { return; }
  c.towns.forEach(function (t) {
    var o = document.createElement('option');
    o.value = t; o.textContent = t;
    sel.appendChild(o);
  });
  sel.value = S.town;
}

function syncControls() {
  $('q').value = S.q;
  $('city').value = S.city;
  fillTowns();
  $('priceMax').value = S.priceMax;
  $('priceInclUnknown').checked = S.inclUnknown;
  $('sort').value = S.sort;
  $('onlyFav').checked = S.onlyFav;
  $('radiusKm').value = S.near ? String(S.near.km) : '10';
  ['cats', 'kinds', 'flags', 'services'].forEach(function (f) {
    var box = { cats: 'catChips', kinds: 'kindChips', flags: 'flagChips',
                services: 'serviceChips' }[f];
    Array.prototype.forEach.call($(box).children, function (b) {
      b.setAttribute('aria-pressed', has(S[f], b.dataset.key) ? 'true' : 'false');
    });
  });
  priceLabel();
  nearLabel();
}

function priceLabel() {
  var v = +S.priceMax;
  $('priceHint').textContent = v >= 6000 ? '（不限）'
    : '≦ ' + v.toLocaleString() + ' 元（平日雙人房價，無則取最低房價）';
}

function nearLabel() {
  var on = !!S.near;
  $('nearRow').hidden = !on;
  $('btnLocate').classList.toggle('on', on && S.near.label === '我的位置');
  $('btnRadius').classList.toggle('on', on && S.near.label !== '我的位置');
  $('btnBounds').classList.toggle('on', S.bounds);
  if (on) {
    $('nearLabel').textContent = S.near.label + ' 周邊';
  }
}

/* ------------------------------------------------------------ 篩選核心 */

function filter() {
  var q = norm(S.q);
  var bnds = (S.bounds && map) ? map.getBounds() : null;
  var out = [];

  for (var i = 0; i < DATA.length; i++) {
    var s = DATA[i];
    if (q && s._s.indexOf(q) < 0) { continue; }
    if (S.city && s.city !== S.city) { continue; }
    if (S.town && s.town !== S.town) { continue; }
    if (S.kinds.length && !has(S.kinds, s.kind)) { continue; }
    if (S.cats.length && !S.cats.every(function (c) { return has(s.categories, c); })) { continue; }
    if (S.onlyFav && !FAV.has(s.id)) { continue; }

    if (S.priceMax < 6000) {
      if (!s._p) { if (!S.inclUnknown) { continue; } }
      else if (s._p > S.priceMax) { continue; }
    }

    if (S.flags.length) {
      var ok = true;
      for (var f = 0; f < FLAG_DEFS.length && ok; f++) {
        if (has(S.flags, FLAG_DEFS[f].key) && !FLAG_DEFS[f].test(s)) { ok = false; }
      }
      if (!ok) { continue; }
    }

    if (S.services.length) {
      var okS = true;
      for (var v = 0; v < S.services.length && okS; v++) {
        if (!has(s.services, S.services[v])) { okS = false; }
      }
      if (!okS) { continue; }
    }

    if (bnds && !bnds.contains([s.lat, s.lng])) { continue; }

    if (S.near) {
      s._d = dist(S.near.lat, S.near.lng, s.lat, s.lng);
      if (S.near.km && s._d > S.near.km) { continue; }
    } else {
      s._d = null;
    }
    out.push(s);
  }
  return out;
}

function sortRows(rows) {
  var cityIdx = {};
  META.cities.forEach(function (c, i) { cityIdx[c.name] = i; });
  var by = {
    distance: function (a, b) { return (a._d == null ? 1e9 : a._d) - (b._d == null ? 1e9 : b._d); },
    price_asc: function (a, b) { return (a._p || 1e9) - (b._p || 1e9); },
    price_desc: function (a, b) { return (b._p || 0) - (a._p || 0); },
    name: function (a, b) { return a.name.localeCompare(b.name, 'zh-Hant'); },
    default: function (a, b) {
      return (cityIdx[a.city] - cityIdx[b.city]) ||
             String(a.town).localeCompare(String(b.town), 'zh-Hant') ||
             a.name.localeCompare(b.name, 'zh-Hant');
    }
  };
  if (S.sort === 'distance' && !S.near) { return rows.sort(by.default); }
  return rows.sort(by[S.sort] || by.default);
}

var applyTimer = null;
function apply(skipURL) {
  var t0 = performance.now();
  VIEW = sortRows(filter());
  renderList(true);
  renderMap();
  $('count').innerHTML = '<strong>' + VIEW.length + '</strong> 家' +
    (VIEW.length !== DATA.length ? ' <span class="n">/ ' + DATA.length + '</span>' : '');
  if (window.__debugPerf) { console.log('filter+render', (performance.now() - t0).toFixed(1), 'ms'); }
  if (!skipURL) {
    clearTimeout(applyTimer);
    applyTimer = setTimeout(writeURL, 250);
  }
}

/* ------------------------------------------------------------ 清單 */

function cardHTML(s) {
  var tags = [];
  s.categories.forEach(function (c) {
    tags.push('<span class="tag">' + CAT_NAME[c] + '</span>');
  });
  if (s.weekday_price) { tags.push('<span class="tag alt">平日雙人 ' + s.weekday_price.toLocaleString() + '</span>'); }
  if (has(s.flags, 'birthday')) { tags.push('<span class="tag">生日券</span>'); }
  if (s.taiwan_host) { tags.push('<span class="tag">好客民宿</span>'); }
  if (s.geo_source === 'township') { tags.push('<span class="tag warn">位置約略</span>'); }

  var price = s.weekday_price ? s.weekday_price.toLocaleString() + ' <small>元</small>'
            : (s.price_low ? s.price_low.toLocaleString() + ' <small>元起</small>' : '');
  var plan = s.plans.length ? s.plans[0].text : '';

  return '<article class="card" data-id="' + s.id + '" tabindex="0">' +
    '<h3>' + esc(s.name) + '</h3>' +
    '<p class="meta">' + esc(s.city) + esc(s.town || '') + ' ・ ' + esc(s.kind) +
      (s.period ? ' ・ 至 ' + esc(s.period) : '') + '</p>' +
    '<div class="side">' +
      (price ? '<div class="price">' + price + '</div>' : '') +
      (s._d != null ? '<div class="dist">' + s._d.toFixed(1) + ' km</div>' : '') +
      '<button type="button" class="fav" data-fav="' + s.id + '" aria-label="收藏">' +
        (FAV.has(s.id) ? '★' : '☆') + '</button>' +
    '</div>' +
    (plan ? '<p class="plan">' + esc(plan) + '</p>' : '') +
    '<div class="tags">' + tags.join('') + '</div>' +
  '</article>';
}

function renderList(reset) {
  var box = $('list');
  if (reset) { box.innerHTML = ''; rendered = 0; $('results').scrollTop = 0; }
  if (!VIEW.length) {
    box.innerHTML = '<p class="empty">找不到符合條件的旅宿。<br>試著放寬價格、清除條件，或把地圖拉遠一點。</p>';
    return;
  }
  var end = Math.min(rendered + CHUNK, VIEW.length);
  var html = '';
  for (var i = rendered; i < end; i++) { html += cardHTML(VIEW[i]); }
  box.insertAdjacentHTML('beforeend', html);
  rendered = end;
  $('spacerBottom').textContent = rendered < VIEW.length
    ? '往下捲動載入更多（已顯示 ' + rendered + ' / ' + VIEW.length + '）' : '';
}

/* ------------------------------------------------------------ 地圖 */

function initMap() {
  if (map) { return; }
  map = L.map('map', { zoomControl: true, preferCanvas: true }).setView([23.7, 121], 7);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19, attribution: '© OpenStreetMap 貢獻者'
  }).addTo(map);
  cluster = L.markerClusterGroup({ chunkedLoading: true, maxClusterRadius: 55,
                                   spiderfyOnMaxZoom: true, showCoverageOnHover: false });
  map.addLayer(cluster);

  map.on('moveend', function () { if (S.bounds) { apply(); } });
  map.on('click', function (e) {
    if (!pickingRadius) { return; }
    setNear(e.latlng.lat, e.latlng.lng, '選定位置');
    pickingRadius = false;
    $('mapHud').hidden = true;
  });
  renderMap();
}

function markerFor(s) {
  var m = MARKERS[s.id];
  if (m) { return m; }
  m = L.marker([s.lat, s.lng], {
    title: s.name,
    opacity: s.geo_source === 'township' ? 0.55 : 1
  });
  m.bindPopup(function () {
    return '<b>' + esc(s.name) + '</b><br>' + esc(s.city) + esc(s.town || '') + ' ・ ' + esc(s.kind) +
      (s.weekday_price ? '<br>平日雙人房 ' + s.weekday_price.toLocaleString() + ' 元' : '') +
      '<br><a href="#" data-open="' + s.id + '">查看方案內容 →</a>';
  });
  MARKERS[s.id] = m;
  return m;
}

function renderMap() {
  if (!map || !cluster) { return; }
  cluster.clearLayers();
  var ms = [];
  for (var i = 0; i < VIEW.length; i++) {
    if (VIEW[i].lat) { ms.push(markerFor(VIEW[i])); }
  }
  cluster.addLayers(ms);
}

function setNear(lat, lng, label) {
  var km = +$('radiusKm').value;
  S.near = { lat: lat, lng: lng, km: km, label: label };
  if (S.sort === 'default') { S.sort = 'distance'; $('sort').value = 'distance'; }
  drawRadius();
  nearLabel();
  apply();
  if (map) { map.setView([lat, lng], km <= 5 ? 13 : km <= 10 ? 12 : 10); }
}

function drawRadius() {
  if (!map) { return; }
  if (radiusCircle) { map.removeLayer(radiusCircle); radiusCircle = null; }
  if (meMarker) { map.removeLayer(meMarker); meMarker = null; }
  if (!S.near) { return; }
  meMarker = L.circleMarker([S.near.lat, S.near.lng], {
    radius: 6, color: '#c2571f', fillColor: '#c2571f', fillOpacity: 1
  }).addTo(map);
  if (S.near.km) {
    radiusCircle = L.circle([S.near.lat, S.near.lng], {
      radius: S.near.km * 1000, color: '#c2571f', weight: 1, fillOpacity: 0.06
    }).addTo(map);
  }
}

/* ------------------------------------------------------------ 詳情 */

function openSheet(id) {
  var s = DATA.filter(function (x) { return x.id === id; })[0];
  if (!s) { return; }
  var q = encodeURIComponent(s.address || (s.city + s.name));
  var tags = s.categories.map(function (c) { return '<span class="tag">' + CAT_NAME[c] + '</span>'; });
  if (s.taiwan_host) { tags.push('<span class="tag">好客民宿</span>'); }
  if (s.stars) { tags.push('<span class="tag">' + s.stars + ' 星級</span>'); }
  s.classes && s.classes.forEach(function (c) { tags.push('<span class="tag warn">' + esc(c) + '</span>'); });

  var kv = '';
  function row(k, v) { if (v) { kv += '<dt>' + k + '</dt><dd>' + v + '</dd>'; } }
  row('地址', esc(s.address));
  row('電話', s.phone_raw ? '<a href="tel:' + esc(String(s.phone_raw).split(/[,\s]/)[0]) + '">' + esc(s.phone_raw) + '</a>' : '');
  row('位置', esc(s.city) + esc(s.town || ''));
  row('平日雙人房', s.weekday_price ? s.weekday_price.toLocaleString() + ' 元' : '');
  row('房價區間', s.price_low ? s.price_low.toLocaleString() + ' – ' + (s.price_high || s.price_low).toLocaleString() + ' 元' : '');
  row('優惠期限', esc(s.period));
  row('登記證號', esc(s.license));
  row('可住人數', s.capacity ? s.capacity + ' 人' : '');
  row('設施服務', (s.services || []).map(esc).join('、'));
  if (GEO_LABEL[s.geo_source]) { row('備註', GEO_LABEL[s.geo_source] + '，請以地址為準'); }

  var plans = s.plans.map(function (p) {
    return '<div class="planBox"><h4>' + CAT_NAME[p.category] +
      (p.period ? ' ・ 優惠期限 ' + esc(p.period) : '') + '</h4>' + esc(p.text) + '</div>';
  }).join('');

  var acts = '<a href="https://www.google.com/maps/search/?api=1&query=' + q +
      '" target="_blank" rel="noopener">在 Google 地圖開啟</a>';
  if (s.phone_raw) {
    acts += '<a class="sec" href="tel:' + esc(String(s.phone_raw).split(/[,\s]/)[0]) + '">撥打電話</a>';
  }
  if (s.website) { acts += '<a class="sec" href="' + esc(s.website) + '" target="_blank" rel="noopener">官方網站</a>'; }
  (s.booking_urls || []).slice(0, 2).forEach(function (u) {
    acts += '<a class="sec" href="' + esc(u) + '" target="_blank" rel="noopener">線上訂房</a>';
  });
  acts += '<a class="sec" href="https://www.taiwanstay.net.tw/TSA/web_page/TSA020200.jsp?hohi_id=' +
    esc(s.id) + '" target="_blank" rel="noopener">旅宿網原始頁</a>';
  acts += '<button type="button" class="sec" data-fav="' + esc(s.id) + '">' +
    (FAV.has(s.id) ? '★ 已收藏' : '☆ 收藏') + '</button>';

  $('sheetBody').innerHTML = '<h2 id="sheetTitle">' + esc(s.name) + '</h2>' +
    '<div class="tags">' + tags.join('') + '</div>' +
    '<dl class="kv">' + kv + '</dl>' + plans +
    '<div class="actions">' + acts + '</div>';
  $('sheet').hidden = false;
  $('sheetClose').focus();
}

/* ------------------------------------------------------------ 網址狀態 */

function writeURL() {
  var p = new URLSearchParams();
  if (S.q) { p.set('q', S.q); }
  if (S.city) { p.set('city', S.city); }
  if (S.town) { p.set('town', S.town); }
  if (S.cats.length) { p.set('cat', S.cats.join(',')); }
  if (S.kinds.length) { p.set('kind', S.kinds.join(',')); }
  if (S.flags.length) { p.set('flag', S.flags.join(',')); }
  if (S.services.length) { p.set('sv', S.services.join(',')); }
  if (S.priceMax < 6000) { p.set('pmax', S.priceMax); }
  if (!S.inclUnknown) { p.set('pu', '0'); }
  if (S.sort !== 'default') { p.set('sort', S.sort); }
  if (S.onlyFav) { p.set('fav', '1'); }
  if (S.near) { p.set('near', S.near.lat.toFixed(5) + ',' + S.near.lng.toFixed(5) + ',' + S.near.km); }
  var qs = p.toString();
  history.replaceState(null, '', qs ? '?' + qs : location.pathname);
}

function readURL() {
  var p = new URLSearchParams(location.search);
  S.q = p.get('q') || '';
  S.city = p.get('city') || '';
  S.town = p.get('town') || '';
  S.cats = (p.get('cat') || '').split(',').filter(Boolean);
  S.kinds = (p.get('kind') || '').split(',').filter(Boolean);
  S.flags = (p.get('flag') || '').split(',').filter(Boolean);
  S.services = (p.get('sv') || '').split(',').filter(Boolean);
  S.priceMax = +(p.get('pmax') || 6000);
  S.inclUnknown = p.get('pu') !== '0';
  S.sort = p.get('sort') || 'default';
  S.onlyFav = p.get('fav') === '1';
  var n = (p.get('near') || '').split(',');
  if (n.length === 3) {
    S.near = { lat: +n[0], lng: +n[1], km: +n[2], label: '指定位置' };
  }
}

/* ------------------------------------------------------------ 事件 */

function bindEvents() {
  var qt = null;
  $('q').addEventListener('input', function (e) {
    S.q = e.target.value;
    clearTimeout(qt);
    qt = setTimeout(apply, 120);
  });

  $('city').addEventListener('change', function (e) {
    S.city = e.target.value; S.town = '';
    fillTowns(); apply();
  });
  $('town').addEventListener('change', function (e) { S.town = e.target.value; apply(); });
  $('sort').addEventListener('change', function (e) { S.sort = e.target.value; apply(); });
  $('onlyFav').addEventListener('change', function (e) { S.onlyFav = e.target.checked; apply(); });
  $('priceInclUnknown').addEventListener('change', function (e) { S.inclUnknown = e.target.checked; apply(); });
  $('priceMax').addEventListener('input', function (e) {
    S.priceMax = +e.target.value; priceLabel(); apply();
  });

  $('btnFilters').addEventListener('click', function () {
    var f = $('barMore');
    f.hidden = !f.hidden;
    $('btnFilters').setAttribute('aria-expanded', String(!f.hidden));
    $('btnFilters').textContent = f.hidden ? '更多條件 ▾' : '收起條件 ▴';
    document.body.classList.toggle('filters-open', !f.hidden);
    if (map) { setTimeout(function () { map.invalidateSize(); }, 60); }
  });

  $('btnClear').addEventListener('click', function () {
    S = { q: '', city: '', town: '', cats: [], kinds: [], flags: [], services: [],
          priceMax: 6000, inclUnknown: true, sort: 'default', onlyFav: false,
          near: null, bounds: false };
    drawRadius(); syncControls(); apply();
  });

  $('btnBounds').addEventListener('click', function () {
    S.bounds = !S.bounds;
    if (S.bounds) { initMap(); showMap(); }
    nearLabel(); apply();
  });

  $('btnRadius').addEventListener('click', function () {
    initMap(); showMap();
    pickingRadius = true;
    var hud = $('mapHud');
    hud.textContent = '在地圖上點一下，設定搜尋範圍的中心點';
    hud.hidden = false;
  });

  $('btnLocate').addEventListener('click', function () {
    if (!navigator.geolocation) { alert('這個瀏覽器不支援定位'); return; }
    var hud = $('mapHud');
    initMap();
    hud.textContent = '定位中…'; hud.hidden = false;
    navigator.geolocation.getCurrentPosition(function (pos) {
      hud.hidden = true;
      setNear(pos.coords.latitude, pos.coords.longitude, '我的位置');
    }, function () {
      hud.hidden = true;
      alert('無法取得位置，請確認已允許瀏覽器定位權限。');
    }, { enableHighAccuracy: true, timeout: 10000 });
  });

  $('radiusKm').addEventListener('change', function (e) {
    if (S.near) { S.near.km = +e.target.value; drawRadius(); apply(); }
  });
  $('btnNearClear').addEventListener('click', function () {
    S.near = null;
    if (S.sort === 'distance') { S.sort = 'default'; $('sort').value = 'default'; }
    drawRadius(); nearLabel(); apply();
  });

  $('results').addEventListener('scroll', function (e) {
    var el = e.target;
    if (rendered < VIEW.length && el.scrollTop + el.clientHeight > el.scrollHeight - 400) {
      renderList(false);
    }
  });

  $('results').addEventListener('click', function (e) {
    var fav = e.target.closest('[data-fav]');
    if (fav) {
      e.stopPropagation();
      toggleFav(fav.dataset.fav);
      fav.textContent = FAV.has(fav.dataset.fav) ? '★' : '☆';
      if (S.onlyFav) { apply(); }
      return;
    }
    var card = e.target.closest('.card');
    if (card) { openSheet(card.dataset.id); }
  });

  $('results').addEventListener('keydown', function (e) {
    var card = e.target.closest('.card');
    if (card && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); openSheet(card.dataset.id); }
  });

  $('results').addEventListener('mouseover', function (e) {
    var card = e.target.closest('.card');
    if (!card || !map) { return; }
    var m = MARKERS[card.dataset.id];
    if (m && m._icon) { m._icon.style.filter = 'hue-rotate(150deg) saturate(2)'; }
  });
  $('results').addEventListener('mouseout', function (e) {
    var card = e.target.closest('.card');
    if (!card) { return; }
    var m = MARKERS[card.dataset.id];
    if (m && m._icon) { m._icon.style.filter = ''; }
  });

  document.addEventListener('click', function (e) {
    var open = e.target.closest('[data-open]');
    if (open) { e.preventDefault(); openSheet(open.dataset.open); }
    var f = e.target.closest('.actions [data-fav]');
    if (f) {
      toggleFav(f.dataset.fav);
      f.textContent = FAV.has(f.dataset.fav) ? '★ 已收藏' : '☆ 收藏';
      renderList(true);
    }
  });

  $('sheetClose').addEventListener('click', function () { $('sheet').hidden = true; });
  $('sheet').addEventListener('click', function (e) {
    if (e.target === $('sheet')) { $('sheet').hidden = true; }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { $('sheet').hidden = true; }
  });

  $('btnGuide').addEventListener('click', function () {
    var g = $('guide');
    g.hidden = !g.hidden;
    $('btnGuide').setAttribute('aria-expanded', String(!g.hidden));
    $('downloadPanel').hidden = true;
  });
  $('btnDownload').addEventListener('click', function () {
    $('downloadPanel').hidden = !$('downloadPanel').hidden;
    $('guide').hidden = true;
  });

  $('btnShare').addEventListener('click', function () {
    navigator.clipboard.writeText(location.href).then(function () {
      $('btnShare').textContent = '已複製 ✓';
      setTimeout(function () { $('btnShare').textContent = '複製查詢連結'; }, 1500);
    });
  });

  var saved = localStorage.getItem('theme');
  if (saved) { document.documentElement.dataset.theme = saved; }
  $('btnTheme').addEventListener('click', function () {
    var cur = document.documentElement.dataset.theme;
    var next = cur === 'dark' ? 'light' : cur === 'light' ? '' : 'dark';
    if (next) { document.documentElement.dataset.theme = next; localStorage.setItem('theme', next); }
    else { delete document.documentElement.dataset.theme; localStorage.removeItem('theme'); }
  });

  Array.prototype.forEach.call($('mobileTabs').children, function (b) {
    b.addEventListener('click', function () {
      if (b.dataset.view === 'map') { showMap(); } else { showList(); }
    });
  });

  window.addEventListener('resize', function () {
    if (window.innerWidth > 860) {
      document.body.classList.remove('view-map');
      document.body.classList.add('view-list');
      initMap();
      if (map) { setTimeout(function () { map.invalidateSize(); }, 50); }
    }
  });
}

function showMap() {
  if (window.innerWidth > 860) { initMap(); return; }
  document.body.classList.remove('view-list');
  document.body.classList.add('view-map');
  setTab('map');
  initMap();
  setTimeout(function () { map.invalidateSize(); }, 60);
}

function showList() {
  document.body.classList.remove('view-map');
  document.body.classList.add('view-list');
  setTab('list');
}

function setTab(v) {
  Array.prototype.forEach.call($('mobileTabs').children, function (b) {
    b.classList.toggle('active', b.dataset.view === v);
  });
}
