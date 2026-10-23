#!/usr/bin/env python3
"""Build the LLM price index: fetch → normalize → data files → static site.

Usage:
    python3 scripts/build.py                # fetch fresh data, build everything
    python3 scripts/build.py --offline      # reuse data/raw.json if present
    python3 scripts/build.py --raw FILE     # use a local source file

No third-party dependencies. Python 3.9+.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import normalize  # noqa: E402
import render  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DIST = ROOT / "dist"
SITE_SRC = ROOT / "site"

SOURCE_URL = ("https://raw.githubusercontent.com/BerriAI/litellm/main/"
              "model_prices_and_context_window.json")

CONFIG = {
    "base_url": os.environ.get("SITE_BASE_URL", "https://moutsea.github.io/llm-price-index/"),
    "repo_url": os.environ.get("SITE_REPO_URL", "https://github.com/moutsea/llm-price-index"),
    "main_site": os.environ.get("MAIN_SITE_URL", "https://costper1m.com"),
    "main_site_label": os.environ.get("MAIN_SITE_LABEL", "costper1m.com"),
}


def fetch_source(raw_path: Path) -> dict:
    """Download the upstream price map, or fall back to a cached copy."""
    if raw_path.exists():
        try:
            return json.loads(raw_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    request = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": "llm-price-index/1.0 (+https://github.com/moutsea/llm-price-index)"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read().decode("utf-8")
    DATA.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(payload, encoding="utf-8")
    return json.loads(payload)


def assign_slugs(models):
    """Give each model a unique filename-safe slug."""
    taken = set()
    for model in models:
        slug = render.slugify(model["id"])
        base, n = slug, 2
        while slug in taken:
            slug = f"{base}-{n}"
            n += 1
        taken.add(slug)
        model["slug"] = slug


def compute_stats(index, raw_count):
    models = index["models"]
    chat = [m for m in models if m["mode"] == "chat"]
    # Spread statistics need at least three sellers: with two, one odd listing
    # is half the sample and the "spread" is just that seller's opinion.
    multi = [m for m in chat if m["provider_count"] > 1]
    comparable = [m for m in chat if m["provider_count"] >= 3 and m["spread"]]
    spreads = sorted(m["spread"] for m in comparable)
    priced = [m for m in models if any(
        o["input"] is not None or o["output"] is not None for o in m["offers"])]
    return {
        "raw_entries": raw_count,
        "price_points": sum(len(m["offers"]) for m in models),
        "models": len(models),
        "chat_models": len(chat),
        "providers": len(index["providers"]),
        "multi_provider": len(multi),
        "comparable": len(comparable),
        "median_spread": round(statistics.median(spreads), 1) if spreads else 0,
        "max_spread": round(max(spreads), 1) if spreads else 0,
        "free_models": sum(1 for m in models if any(o["free"] for o in m["offers"])),
        "priced_models": len(priced),
    }


def write_data(index, stats, source_meta):
    DATA.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": stats["generated_at"],
        "source": source_meta,
        "stats": stats,
        "providers": index["providers"],
        "models": [
            {k: v for k, v in m.items() if k != "slug"} | {"slug": m["slug"]}
            for m in index["models"]
        ],
    }
    (DATA / "prices.json").write_text(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")

    with (DATA / "prices.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "model_id", "vendor", "mode", "provider", "input_per_1m",
            "output_per_1m", "cache_read_per_1m", "cache_write_per_1m",
            "context", "free", "deprecated", "source_model_id",
        ])
        for model in index["models"]:
            for offer in model["offers"]:
                writer.writerow([
                    model["family"], model["vendor"], model["mode"], offer["provider"],
                    _fmt(offer["input"]), _fmt(offer["output"]),
                    _fmt(offer["cache_read"]), _fmt(offer["cache_write"]),
                    model["context"] or "", int(offer["free"]), int(offer["deprecated"]),
                    offer["raw_id"],
                ])

    (DATA / "meta.json").write_text(
        json.dumps({"generated_at": stats["generated_at"], "stats": stats, "source": source_meta},
                   indent=2), encoding="utf-8")


def _fmt(value):
    return "" if value is None else f"{value:g}"


def build_site(index, stats, cfg):
    if DIST.exists():
        for path in sorted(DIST.rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
    DIST.mkdir(parents=True, exist_ok=True)
    (DIST / "m").mkdir(exist_ok=True)
    (DIST / "p").mkdir(exist_ok=True)

    for asset in ("style.css", "app.js"):
        (DIST / asset).write_text((SITE_SRC / asset).read_text(encoding="utf-8"), encoding="utf-8")

    root_cfg = dict(cfg, asset_prefix="", generated_at=stats["generated_at"])
    sub_cfg = dict(cfg, asset_prefix="../", generated_at=stats["generated_at"])

    (DIST / "index.html").write_text(
        render.render_index(index["models"], index["providers"], stats, root_cfg), encoding="utf-8")
    (DIST / "providers.html").write_text(
        render.render_providers(index["providers"], stats, root_cfg), encoding="utf-8")
    (DIST / "compare.html").write_text(
        render.render_compare(index["models"], root_cfg), encoding="utf-8")

    by_vendor = {}
    for model in index["models"]:
        by_vendor.setdefault((model["vendor"], model["mode"]), []).append(model)

    for model in index["models"]:
        pool = by_vendor.get((model["vendor"], model["mode"]), [])
        related = sorted(
            (o for o in pool if o["id"] != model["id"] and o["in_min"] is not None),
            key=lambda o: abs(o["in_min"] - (model["in_min"] or 0)),
        )[:8]
        (DIST / "m" / f"{model['slug']}.html").write_text(
            render.render_model(model, sub_cfg, related), encoding="utf-8")

    for provider in index["providers"]:
        (DIST / "p" / f"{render.slugify(provider['id'])}.html").write_text(
            render.render_provider_page(provider, index["models"], sub_cfg), encoding="utf-8")

    (DIST / "sitemap.xml").write_text(
        render.render_sitemap(index["models"], index["providers"], cfg), encoding="utf-8")
    (DIST / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {cfg['base_url']}sitemap.xml\n", encoding="utf-8")


def write_readme(index, stats, cfg):
    """Regenerate the data block inside README.md between the markers."""
    chat = [m for m in index["models"] if m["mode"] == "chat" and m["spread"] and m["provider_count"] > 1]
    top = sorted(chat, key=lambda m: -m["spread"])[:15]
    rows = "\n".join(
        f"| [{m['family']}]({cfg['base_url']}m/{m['slug']}.html) | "
        f"{render.VENDOR_LABEL.get(m['vendor'], m['vendor'])} | {m['provider_count']} | "
        f"{render.money(m['in_min'])} | {render.money(m['in_max'])} | **{m['spread']:.1f}×** |"
        for m in top
    )
    block = f"""<!-- BEGIN DATA -->
_Last rebuilt: {stats['generated_at']}_

| | |
|---|---|
| Price points | **{stats['price_points']:,}** |
| Model families | **{stats['models']:,}** ({stats['chat_models']:,} chat) |
| Providers | **{stats['providers']}** |
| Comparable across providers | **{stats['multi_provider']:,}** |
| Median price spread | **{stats['median_spread']}×** |
| Widest spread | **{stats['max_spread']}×** |

### Widest spreads: the same model, different prices

| Model | Vendor | Sellers | Cheapest input /1M | Priciest input /1M | Spread |
|---|---|---:|---:|---:|---:|
{rows}
<!-- END DATA -->"""
    readme = ROOT / "README.md"
    begin, end = "<!-- BEGIN DATA -->", "<!-- END DATA -->"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        if begin in text and end in text:
            head = text.split(begin)[0]
            tail = text.split(end)[1]
            readme.write_text(head + block + tail, encoding="utf-8")
            return
    readme.write_text((ROOT / "README.template.md").read_text(encoding="utf-8")
                      .replace(begin, block), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true",
                        help="use data/raw.json instead of downloading")
    parser.add_argument("--raw", type=Path, help="path to a LiteLLM-format price map")
    parser.add_argument("--no-site", action="store_true", help="skip HTML generation")
    args = parser.parse_args()

    raw_path = args.raw or (DATA / "raw.json")
    if args.raw and args.raw.exists():
        raw = json.loads(args.raw.read_text(encoding="utf-8"))
    elif args.offline:
        if not raw_path.exists():
            print("error: --offline needs data/raw.json", file=sys.stderr)
            return 1
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
    else:
        raw = fetch_source(raw_path)

    print(f"source entries: {len(raw):,}")
    index = normalize.build_index(raw)
    assign_slugs(index["models"])
    stats = compute_stats(index, len(raw))
    stats["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    source_meta = {
        "name": "LiteLLM model_prices_and_context_window.json",
        "url": SOURCE_URL,
        "license": "MIT",
        "copyright": "Copyright (c) 2023 Berri AI",
    }
    write_data(index, stats, source_meta)
    print(f"models: {stats['models']:,} | providers: {stats['providers']} | "
          f"price points: {stats['price_points']:,} | multi-provider: {stats['multi_provider']:,}")

    if not args.no_site:
        build_site(index, stats, CONFIG)
        print(f"site: {len(index['models']):,} model pages + "
              f"{len(index['providers'])} provider pages → dist/")
    write_readme(index, stats, CONFIG)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
