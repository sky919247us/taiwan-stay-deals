# -*- coding: utf-8 -*-
"""產生網站圖示：favicon.ico、PNG 各尺寸、SVG 與 webmanifest。

圖案是「地圖圖釘」，用品牌綠底＋白色圖釘，16px 也認得出來。
先畫在 1024px 再縮圖（LANCZOS），邊緣才不會鋸齒。
執行：python scripts/make_icons.py
"""
import os, json
from PIL import Image, ImageDraw
from config import ROOT

PUB = os.path.join(ROOT, "public")
BRAND = (31, 111, 92, 255)        # #1F6F5C
WHITE = (255, 255, 255, 255)
ACCENT = (194, 87, 31, 255)       # #C2571F

S = 1024                          # 母圖尺寸


def rounded_bg(size, radius_ratio, color):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size - 1, size - 1],
                        radius=int(size * radius_ratio), fill=color)
    return img


# 圖釘幾何（以 1024 母圖為基準），SVG 與 PNG 共用同一組數字才會長得一樣
PIN_R = 0.205        # 圓頭半徑
PIN_CY = 0.385       # 圓心高度
PIN_TIP = 2.10       # 尖端長度（相對半徑）
PIN_HOLE = 0.42      # 中間挖洞半徑（相對半徑）
BAR_Y, BAR_W, BAR_H = 0.875, 0.30, 0.050


def geometry(size, scale=1.0, shift=0.0):
    r = size * PIN_R * scale
    cx = size / 2
    cy = size * PIN_CY * scale + size * shift
    return {
        "cx": cx, "cy": cy, "r": r,
        "tip": cy + r * PIN_TIP,
        "wing": r * 0.74,
        "shoulder": cy + r * 0.70,
        "hole": r * PIN_HOLE,
        "bar": (cx - size * BAR_W * scale / 2, size * BAR_Y * scale + size * shift,
                cx + size * BAR_W * scale / 2,
                size * BAR_Y * scale + size * shift + size * BAR_H * scale),
    }


def draw_pin(img, g):
    """圖釘＝上方圓形 ＋ 下方尖角，中間挖一個洞；底下一抹橘色當地面。"""
    d = ImageDraw.Draw(img)
    d.ellipse([g["cx"] - g["r"], g["cy"] - g["r"], g["cx"] + g["r"], g["cy"] + g["r"]],
              fill=WHITE)
    d.polygon([(g["cx"] - g["wing"], g["shoulder"]),
               (g["cx"] + g["wing"], g["shoulder"]),
               (g["cx"], g["tip"])], fill=WHITE)
    d.ellipse([g["cx"] - g["hole"], g["cy"] - g["hole"],
               g["cx"] + g["hole"], g["cy"] + g["hole"]], fill=BRAND)
    x0, y0, x1, y1 = g["bar"]
    d.rounded_rectangle([x0, y0, x1, y1], radius=(y1 - y0) / 2, fill=ACCENT)


def master(scale=1.0, shift=0.0, radius=0.22):
    """scale < 1 給 maskable 用（Android 會裁掉外圈約 10%，且背景要滿版）。"""
    img = rounded_bg(S, radius, BRAND)
    draw_pin(img, geometry(S, scale, shift))
    return img


SVG_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" role="img" aria-label="國旅補助旅宿地圖">
  <rect width="1024" height="1024" rx="225" fill="#1F6F5C"/>
  <circle cx="{cx:.0f}" cy="{cy:.0f}" r="{r:.0f}" fill="#fff"/>
  <polygon points="{lx:.0f},{sy:.0f} {rx:.0f},{sy:.0f} {cx:.0f},{tip:.0f}" fill="#fff"/>
  <circle cx="{cx:.0f}" cy="{cy:.0f}" r="{hole:.0f}" fill="#1F6F5C"/>
  <rect x="{bx:.0f}" y="{by:.0f}" width="{bw:.0f}" height="{bh:.0f}" rx="{br:.0f}" fill="#C2571F"/>
</svg>
"""


def make_svg():
    g = geometry(1024)
    x0, y0, x1, y1 = g["bar"]
    return SVG_TEMPLATE.format(
        cx=g["cx"], cy=g["cy"], r=g["r"], tip=g["tip"], hole=g["hole"],
        lx=g["cx"] - g["wing"], rx=g["cx"] + g["wing"], sy=g["shoulder"],
        bx=x0, by=y0, bw=x1 - x0, bh=y1 - y0, br=(y1 - y0) / 2)


MANIFEST = {
    "name": "2026 國旅補助旅宿地圖",
    "short_name": "國旅補助地圖",
    "description": "115 年國旅平日住宿獎助與平價優質旅宿參與名單，支援地圖、附近與價格區間搜尋。",
    "lang": "zh-Hant-TW",
    "start_url": "./",
    "scope": "./",
    "display": "standalone",
    "orientation": "any",
    "background_color": "#f5f6f4",
    "theme_color": "#1f6f5c",
    "icons": [
        {"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"},
        {"src": "icon-512-maskable.png", "sizes": "512x512", "type": "image/png",
         "purpose": "maskable"},
        {"src": "icon.svg", "sizes": "any", "type": "image/svg+xml"},
    ],
}


def main():
    img = master()

    # favicon.ico：一個檔包多種尺寸，小尺寸交給 Windows／瀏覽器挑
    ico_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.resize((256, 256), Image.LANCZOS).save(
        os.path.join(PUB, "favicon.ico"), format="ICO", sizes=ico_sizes)

    for name, px in [("favicon-32.png", 32), ("favicon-16.png", 16),
                     ("apple-touch-icon.png", 180),
                     ("icon-192.png", 192), ("icon-512.png", 512)]:
        img.resize((px, px), Image.LANCZOS).save(os.path.join(PUB, name), optimize=True)

    # maskable：內容縮到安全區內，Android 裁圓角才不會切到圖釘
    master(scale=0.80, shift=0.10, radius=0).resize((512, 512), Image.LANCZOS).save(
        os.path.join(PUB, "icon-512-maskable.png"), optimize=True)

    with open(os.path.join(PUB, "icon.svg"), "w", encoding="utf-8") as f:
        f.write(make_svg())
    with open(os.path.join(PUB, "site.webmanifest"), "w", encoding="utf-8") as f:
        json.dump(MANIFEST, f, ensure_ascii=False, indent=2)

    for n in ("favicon.ico", "icon.svg", "apple-touch-icon.png", "icon-192.png",
              "icon-512.png", "icon-512-maskable.png", "site.webmanifest"):
        print("  %-26s %6d bytes" % (n, os.path.getsize(os.path.join(PUB, n))))
    print("[完成] 圖示已產生於 public/")


if __name__ == "__main__":
    main()
