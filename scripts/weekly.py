# -*- coding: utf-8 -*-
"""每週在本機跑完整條管線，驗收通過才 commit & push。

為什麼在本機跑而不是 GitHub Actions：評分與抽價需要 Google 與 OpenRouter
的金鑰，放進雲端的 repo secrets 等於多一組要保管的東西，也多幾種失敗方式。
本機有金鑰、有 Chromium，跑完直接推，Cloudflare 收到 push 就自動部署。

用法：
  python scripts/weekly.py            # 完整跑一輪並推上去
  python scripts/weekly.py --no-push  # 只跑不推（先看結果）
  python scripts/weekly.py --quick    # 跳過耗時的抽價與渲染，只更新名單

各階段都會用快取，所以第二次之後只處理「這週新增的旅宿」，很快。
"""
import os, sys, time, argparse, subprocess
from config import ROOT

PY = sys.executable
HERE = os.path.dirname(os.path.abspath(__file__))

# (檔名, 參數, 說明, 是否為耗時階段)
#
# webprice_js.py 不放進預設流程：185 家渲染只換到 6 筆價格，投報率太低，
# 卻要多花 35 分鐘並依賴 Chromium。需要時用 --with-render 才跑。
STAGES = [
    ("scrape.py",    [], "抓取官網名單", False),
    ("enrich.py",    [], "比對開放資料、補座標", False),
    ("extract.py",   [], "從方案文字抽結構化欄位", False),
    ("places.py",    [], "Google 評分（只查新增的）", True),
    ("planprice.py", [], "方案文字抽價（只查新增的）", True),
    ("webprice.py",  [], "官網抽價（只查新增的）", True),
    # SerpApi 免費方案每月 250 次，留一點緩衝
    ("otaprice.py",  ["--budget", "200"], "訂房平台參考價（只查新增的）", True),
    ("manual.py",    [], "更新人工查核清單", False),
    ("build.py",     [], "產出網站資料與下載檔", False),
    ("verify.py",    [], "驗收", False),
]

RENDER_STAGE = ("webprice_js.py", [], "無頭瀏覽器渲染抽價", True)


def run(script, label, extra=()):
    print("\n" + "=" * 60)
    print("▶ %s（%s）" % (label, script))
    print("=" * 60, flush=True)
    t0 = time.time()
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([PY, os.path.join(HERE, script)] + list(extra), cwd=ROOT, env=env)
    print("  ── 耗時 %.0f 秒，結束碼 %d" % (time.time() - t0, r.returncode), flush=True)
    return r.returncode


def git(*args, check=True):
    r = subprocess.run(["git"] + list(args), cwd=ROOT, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit("git %s 失敗：%s" % (" ".join(args), r.stderr.strip()))
    return r.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-push", action="store_true", help="跑完不要 commit & push")
    ap.add_argument("--quick", action="store_true", help="跳過耗時的抽價階段，只更新名單")
    ap.add_argument("--with-render", action="store_true",
                    help="額外跑無頭瀏覽器渲染（很慢、收穫少，預設不跑）")
    args = ap.parse_args()

    # 先把遠端的變更拉下來，避免和 Actions 或另一台機器的提交打架
    if not args.no_push:
        git("fetch", "origin")
        behind = git("rev-list", "--count", "HEAD..origin/main")
        if behind != "0":
            print("[準備] 遠端有 %s 筆新提交，先 rebase" % behind)
            git("rebase", "origin/main")

    stages = list(STAGES)
    if args.with_render:
        stages.insert(-3, RENDER_STAGE)      # 排在 manual／build／verify 之前

    for script, extra, label, slow in stages:
        if args.quick and slow:
            print("\n（--quick：跳過 %s）" % label)
            continue
        code = run(script, label, extra)
        if code != 0:
            # 抓取與驗收失敗代表資料有問題，不能繼續；抽價類失敗只是少補幾筆
            if script in ("scrape.py", "enrich.py", "build.py", "verify.py"):
                raise SystemExit("\n✗ %s 失敗，中止。網站資料維持上一版不動。" % label)
            print("  ⚠ %s 失敗，略過繼續（少補幾筆價格不影響網站）" % label)

    if args.no_push:
        print("\n完成（--no-push，沒有提交）")
        return

    if not git("status", "--porcelain"):
        print("\n完成：資料沒有變動，不需要提交。")
        return

    git("add", "-A")
    today = time.strftime("%Y-%m-%d")
    import json
    meta = json.load(open(os.path.join(ROOT, "public", "data", "meta.json"), encoding="utf-8"))
    ps = meta.get("price_stat", {})
    priced = sum(v for k, v in ps.items() if k != "none")
    msg = ("data: %s 更新（共 %d 家，有房價 %d 家，有評分 %d 家）"
           % (today, meta["total"], priced, meta.get("rating_count", 0)))
    subprocess.run(["git", "commit", "-q", "-m", msg], cwd=ROOT, check=True)
    git("push", "origin", "main")
    print("\n✓ 已推送：%s" % msg)
    print("  Cloudflare Pages 會自動重新部署，約一分鐘後生效。")


if __name__ == "__main__":
    main()
