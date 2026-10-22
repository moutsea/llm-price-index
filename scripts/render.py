"""Static HTML rendering for the price index site.

Every page is fully server-rendered: the tables carry the data in the HTML so
the site is indexable and readable without JavaScript. JavaScript only adds
sorting, filtering and the calculator.
"""

from __future__ import annotations

import html
import json
import re

MODE_LABEL = {
    "chat": "Chat",
    "completion": "Completion",
    "embedding": "Embedding",
    "image_generation": "Image generation",
    "image_edit": "Image edit",
    "audio_transcription": "Audio transcription",
    "audio_speech": "Speech",
    "rerank": "Rerank",
    "responses": "Responses",
    "realtime": "Realtime",
    "video_generation": "Video generation",
    "ocr": "OCR",
    "search": "Search",
    "evaluation": "Evaluation",
    "extraction": "Extraction",
    "guardrail": "Guardrail",
    "moderation": "Moderation",
    "vector_store": "Vector store",
}

VENDOR_LABEL = {
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "google": "Google",
    "xai": "xAI",
    "deepseek": "DeepSeek",
    "meta": "Meta",
    "alibaba": "Alibaba",
    "mistral": "Mistral",
    "moonshot": "Moonshot",
    "zhipu": "Zhipu",
    "cohere": "Cohere",
    "amazon": "Amazon",
    "microsoft": "Microsoft",
    "ai21": "AI21",
    "other": "Other",
}


def esc(value):
    return html.escape(str(value), quote=True)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "model"


def money(value, suffix=""):
    """Format a USD-per-1M-tokens figure compactly."""
    if value is None:
        return "—"
    if value == 0:
        return "free"
    if value >= 100:
        text = f"${value:,.0f}"
    elif value >= 1:
        text = f"${value:,.2f}"
    elif value >= 0.01:
        text = f"${value:.3f}"
    else:
        text = f"${value:.4f}"
    return text + suffix


def compact(n):
    if n is None:
        return "—"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def base_head(cfg, title, description, canonical, extra_head=""):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}">
<meta name="twitter:card" content="summary">
<link rel="stylesheet" href="{cfg['asset_prefix']}style.css">
{extra_head}</head>
<body>
<header class="site"><div class="wrap">
<a class="logo" href="{cfg['asset_prefix']}index.html">llm<span>price</span>index</a>
<nav class="site">
<a href="{cfg['asset_prefix']}index.html">Prices</a>
<a href="{cfg['asset_prefix']}providers.html">Providers</a>
<a href="{cfg['asset_prefix']}compare.html">Calculator</a>
<a href="{cfg['repo_url']}">GitHub</a>
</nav>
</div></header>
<main><div class="wrap">
"""


def base_foot(cfg):
    return f"""</div></main>
<footer class="site"><div class="wrap">
<p>Open dataset of LLM API prices, rebuilt from
<a href="https://github.com/BerriAI/litellm">LiteLLM</a>'s
<a href="https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json">model price map</a>
(MIT). Normalization and site by <a href="{cfg['main_site']}">{cfg['main_site_label']}</a>.</p>
<p>Prices are as reported by each provider and may lag actual billing. Verify before you buy.
Generated {esc(cfg['generated_at'])}.</p>
</div></footer>
<script src="{cfg['asset_prefix']}app.js" defer></script>
</body>
</html>
"""


def stat_block(items):
    cells = "".join(
        f'<div class="stat"><span class="n">{esc(value)}</span>'
        f'<span class="k">{esc(label)}</span></div>'
        for value, label in items
    )
    return f'<div class="stats">{cells}</div>'


def offer_rows(model, cfg, link_provider=True):
    rows = []
    reference = model.get("first_party") or {}
    for offer in sorted(model["offers"], key=lambda o: (o["input"] if o["input"] is not None else 9e9, o["provider"])):
        provider = offer["provider"]
        pid = slugify(provider)
        prov_html = (f'<a href="{cfg["asset_prefix"]}p/{pid}.html">{esc(provider)}</a>'
                     if link_provider else esc(provider))
        marker = ""
        if reference and offer["input"] is not None and reference.get("input"):
            if offer["input"] <= reference["input"] * 1.001:
                marker = ' <span class="chip badge-fp">list price</span>'
        rows.append(
            "<tr>"
            f'<td>{prov_html}{marker}</td>'
            f'<td class="num" data-v="{offer["input"] if offer["input"] is not None else ""}">{money(offer["input"])}</td>'
            f'<td class="num" data-v="{offer["output"] if offer["output"] is not None else ""}">{money(offer["output"])}</td>'
            f'<td class="num" data-v="{offer["cache_read"] if offer["cache_read"] is not None else ""}">{money(offer["cache_read"])}</td>'
            f'<td class="num" data-v="{offer["cache_write"] if offer["cache_write"] is not None else ""}">{money(offer["cache_write"])}</td>'
            f'<td class="mono muted">{esc(offer["raw_id"])}</td>'
            "</tr>"
        )
    return "".join(rows)


OFFER_HEAD = (
    "<thead><tr>"
    '<th data-sort>Provider</th>'
    '<th class="num" data-sort>Input /1M</th>'
    '<th class="num" data-sort>Output /1M</th>'
    '<th class="num" data-sort>Cache read</th>'
    '<th class="num" data-sort>Cache write</th>'
    "<th>Source model id</th>"
    "</tr></thead>"
)


def render_index(models, providers, stats, cfg):
    chat = [m for m in models if m["mode"] == "chat"]
    paid = [m for m in chat if m["in_min"] is not None]
    cheapest = sorted(paid, key=lambda m: (m["in_min"], m["out_min"] or 0))[:40]
    spreads = sorted(
        (m for m in chat if m["spread"] and m["provider_count"] > 1),
        key=lambda m: -m["spread"],
    )[:40]
    widely = sorted(
        (m for m in chat if m["provider_count"] > 1),
        key=lambda m: (-m["provider_count"], m["family"]),
    )[:30]

    def main_rows(rows):
        out = []
        for m in rows:
            href = f'{cfg["asset_prefix"]}m/{m["slug"]}.html'
            fp = m.get("first_party")
            fp_html = (f'<span class="chip badge-fp">{esc(fp["provider"])}</span>' if fp else "")
            out.append(
                f'<tr data-name="{esc(m["family"] + " " + m["vendor"])}">'
                f'<td><a href="{href}">{esc(m["family"])}</a></td>'
                f'<td class="muted">{esc(VENDOR_LABEL.get(m["vendor"], m["vendor"]))}</td>'
                f'<td class="num" data-v="{m["provider_count"]}">{m["provider_count"]}</td>'
                f'<td class="num" data-v="{m["in_min"] if m["in_min"] is not None else ""}">{money(m["in_min"])}</td>'
                f'<td class="num" data-v="{m["out_min"] if m["out_min"] is not None else ""}">{money(m["out_min"])}</td>'
                f'<td class="num" data-v="{m["context"] or 0}">{compact(m["context"])}</td>'
                f'<td>{fp_html}</td>'
                "</tr>"
            )
        return "".join(out)

    def spread_rows():
        out = []
        for m in spreads:
            href = f'{cfg["asset_prefix"]}m/{m["slug"]}.html'
            out.append(
                f'<tr data-name="{esc(m["family"] + " " + m["vendor"])}">'
                f'<td><a href="{href}">{esc(m["family"])}</a></td>'
                f'<td class="muted">{esc(VENDOR_LABEL.get(m["vendor"], m["vendor"]))}</td>'
                f'<td class="num" data-v="{m["provider_count"]}">{m["provider_count"]}</td>'
                f'<td class="num" data-v="{m["in_min"]}">{money(m["in_min"])}</td>'
                f'<td class="num" data-v="{m["in_max"]}">{money(m["in_max"])}</td>'
                f'<td class="num"><span class="badge-spread">{m["spread"]:.1f}×</span></td>'
                "</tr>"
            )
        return "".join(out)

    def widely_rows():
        out = []
        for m in widely:
            href = f'{cfg["asset_prefix"]}m/{m["slug"]}.html'
            spread = f'{m["spread"]:.1f}×' if m["spread"] else "—"
            out.append(
                f'<tr data-name="{esc(m["family"] + " " + m["vendor"])}">'
                f'<td><a href="{href}">{esc(m["family"])}</a></td>'
                f'<td class="muted">{esc(VENDOR_LABEL.get(m["vendor"], m["vendor"]))}</td>'
                f'<td class="num" data-v="{m["provider_count"]}">{m["provider_count"]}</td>'
                f'<td class="num" data-v="{m["in_min"] if m["in_min"] is not None else ""}">{money(m["in_min"])}</td>'
                f'<td class="num" data-v="{m["out_min"] if m["out_min"] is not None else ""}">{money(m["out_min"])}</td>'
                f'<td class="num"><span class="badge-spread">{spread}</span></td>'
                "</tr>"
            )
        return "".join(out)

    model_rows = []
    for m in chat:
        model_rows.append(
            f'<tr data-name="{esc(m["family"] + " " + m["vendor"] + " " + " ".join(o["provider"] for o in m["offers"]))}">'
            f'<td><a href="{cfg["asset_prefix"]}m/{m["slug"]}.html">{esc(m["family"])}</a></td>'
            f'<td class="muted">{esc(VENDOR_LABEL.get(m["vendor"], m["vendor"]))}</td>'
            f'<td class="num" data-v="{m["provider_count"]}">{m["provider_count"]}</td>'
            f'<td class="num" data-v="{m["in_min"] if m["in_min"] is not None else ""}">{money(m["in_min"])}</td>'
            f'<td class="num" data-v="{m["in_max"] if m["in_max"] is not None else ""}">{money(m["in_max"])}</td>'
            f'<td class="num" data-v="{m["out_min"] if m["out_min"] is not None else ""}">{money(m["out_min"])}</td>'
            f'<td class="num" data-v="{m["spread"] or 0}">{(f"{m['spread']:.1f}×" if m["spread"] else "—")}</td>'
            f'<td class="num" data-v="{m["context"] or 0}">{compact(m["context"])}</td>'
            "</tr>"
        )

    ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": "LLM API price index",
        "description": "Normalized per-token prices for language models across providers, "
                       "rebuilt daily from LiteLLM's open price map.",
        "url": cfg["base_url"],
        "license": "https://opensource.org/licenses/MIT",
        "isAccessibleForFree": True,
        "keywords": ["LLM pricing", "API cost", "cost per 1M tokens", "model comparison"],
        "creator": {"@type": "Organization", "name": cfg["main_site_label"], "url": cfg["main_site"]},
    }, separators=(",", ":"))

    extra = (f'<script type="application/ld+json">{ld}</script>'
             '<meta name="robots" content="index,follow">')

    body = f"""<h1>What every LLM actually costs</h1>
<p class="lede">Normalized prices for <strong>{stats['models']}</strong> model families across
<strong>{stats['providers']}</strong> providers, rebuilt daily from an open price map.
The same model is often sold at wildly different prices — this is where you see it.</p>
{stat_block([
    (f"{stats['price_points']:,}", "price points"),
    (f"{stats['models']:,}", "model families"),
    (str(stats["providers"]), "providers"),
    (f"{stats['multi_provider']:,}", "cross-provider"),
    (f"{stats['max_spread']:.0f}×" if stats.get("max_spread") else "—", "widest spread"),
])}
<p class="note">All prices in USD per 1 million tokens. Free = published at $0.00 by the provider.</p>

<div class="callout"><p><strong>Why the spread matters.</strong> For
<strong>{stats['multi_provider']}</strong> model families you can pick a provider.
Half of them sit within <strong>{stats['median_spread']}×</strong> of each other — hosting
a frontier model is a commodity and sellers track the list price. The other half does not:
the widest gap in this dataset is <strong>{stats['max_spread']:.0f}×</strong>, and it is
almost always the same open-weight model sold cheap by an inference host and expensive by
someone who wrapped it in a product.</p></div>

<h2>Widest provider spread</h2>
<p class="note">Same model family, different providers. Sorted by the ratio between the cheapest and most expensive input price.</p>
<div class="tablewrap"><table>
<thead><tr><th data-sort>Model</th><th data-sort>Vendor</th><th class="num" data-sort>Sellers</th>
<th class="num" data-sort>Cheapest in</th><th class="num" data-sort>Priciest in</th><th class="num" data-sort>Spread</th></tr></thead>
<tbody>{spread_rows()}</tbody></table></div>

<h2>Most widely sold models</h2>
<p class="note">The models the most providers bother to host — the ones buyers actually compare.</p>
<div class="tablewrap"><table>
<thead><tr><th data-sort>Model</th><th data-sort>Vendor</th><th class="num" data-sort>Sellers</th>
<th class="num" data-sort>Cheapest in</th><th class="num" data-sort>Cheapest out</th>
<th class="num" data-sort>Spread</th></tr></thead>
<tbody>{widely_rows()}</tbody></table></div>

<h2>Cheapest models</h2>
<p class="note">Chat models ranked by input price. The long tail of open-weight models is far cheaper than any frontier model.</p>
<div class="tablewrap"><table>
<thead><tr><th data-sort>Model</th><th data-sort>Vendor</th><th class="num" data-sort>Sellers</th>
<th class="num" data-sort>Input /1M</th><th class="num" data-sort>Output /1M</th>
<th class="num" data-sort>Context</th><th>Sells directly</th></tr></thead>
<tbody>{main_rows(cheapest)}</tbody></table></div>

<h2>All chat models</h2>
<p class="note"><span id="model-count">{len(chat):,}</span> models. Type to filter by model, vendor or provider.</p>
<input class="search" id="model-search" type="search" placeholder="Filter models, vendors, providers…" data-filter="all-models" data-count="model-count" autocomplete="off">
<div class="tablewrap"><table>
<thead><tr><th data-sort>Model</th><th data-sort>Vendor</th><th class="num" data-sort>Sellers</th>
<th class="num" data-sort>Min in</th><th class="num" data-sort>Max in</th>
<th class="num" data-sort>Min out</th><th class="num" data-sort>Spread</th>
<th class="num" data-sort>Context</th></tr></thead>
<tbody id="all-models">{''.join(model_rows)}</tbody></table></div>
"""
    title = "LLM API price index — cost per 1M tokens across 100+ providers"
    desc = (f"Open, normalized dataset of LLM API prices: {stats['price_points']:,} price points, "
            f"{stats['models']:,} model families, {stats['providers']} providers. "
            "Compare cost per 1M tokens and see provider markup.")
    return (base_head(cfg, title, desc, f"{cfg['base_url']}index.html", extra)
            + body + base_foot(cfg))


def related_html(model, related, cfg):
    if not related:
        return ""
    items = "".join(
        f'<li><a href="{cfg["asset_prefix"]}m/{m["slug"]}.html">{esc(m["family"])}</a> '
        f'<span class="muted">{money(m["in_min"])} in / {money(m["out_min"])} out</span></li>'
        for m in related
    )
    vendor = VENDOR_LABEL.get(model["vendor"], model["vendor"])
    return (f'<h2>Other {esc(vendor)} models</h2>'
            f'<p class="note">Closest by input price.</p><ul class="rel">{items}</ul>')


def render_model(model, cfg, related=()):
    href_prefix = cfg["asset_prefix"]
    offers_table = f'<div class="tablewrap"><table>{OFFER_HEAD}<tbody>{offer_rows(model, cfg)}</tbody></table></div>'
    spread_note = ""
    if model["spread"] and model["spread"] > 1.01:
        spread_note = (
            f'<div class="callout"><p><strong>{model["spread"]:.1f}× spread.</strong> '
            f'The cheapest provider charges {money(model["in_min"])}/1M input; the priciest asks '
            f'{money(model["in_max"])}/1M for the same model. On 10M input tokens that is '
            f'{money((model["in_max"] - model["in_min"]) * 10)} of difference.</p></div>'
        )
    fp = model.get("first_party")
    fp_line = ""
    if fp:
        fp_line = (f'<p class="note">First-party price (sold by '
                   f'{esc(VENDOR_LABEL.get(model["vendor"], model["vendor"]))} itself): '
                   f'{money(fp["input"])}/1M input, {money(fp["output"])}/1M output.</p>')

    body = f"""<p class="crumbs"><a href="{href_prefix}index.html">Prices</a> / {esc(model["family"])}</p>
<h1>{esc(model["family"])}</h1>
<p class="lede">{esc(VENDOR_LABEL.get(model["vendor"], model["vendor"]))} ·
{esc(MODE_LABEL.get(model["mode"], model["mode"]))} ·
{compact(model["context"])} context ·
sold by {model["provider_count"]} provider{"s" if model["provider_count"] != 1 else ""}</p>
{stat_block([
    (money(model["in_min"]), "cheapest input /1M"),
    (money(model["out_min"]), "cheapest output /1M"),
    (f'{model["spread"]:.1f}×' if model["spread"] else "—", "price spread"),
    (compact(model["context"]), "context"),
])}
{fp_line}
{spread_note}
<h2>Every provider's price</h2>
<p class="note">One row per provider and price point. <span class="chip badge-fp">list price</span>
means that seller charges the same as the vendor's own published price. "Source model id" is
the exact key in the source dataset, so you can verify any number yourself.</p>
{offers_table}
<h2>Cost at volume</h2>
<p class="note">At the cheapest available input price.</p>
<div class="tablewrap"><table>
<thead><tr><th>Volume</th><th class="num">Input cost</th><th class="num">Output cost</th><th class="num">Total</th></tr></thead>
<tbody>
{''.join(f'<tr><td>{label}</td>'
         f'<td class="num">{money((tokens / 1e6) * (model["in_min"] or 0))}</td>'
         f'<td class="num">{money((tokens / 1e6) * (model["out_min"] or 0))}</td>'
         f'<td class="num"><strong>{money((tokens / 1e6) * ((model["in_min"] or 0) + (model["out_min"] or 0)))}</strong></td></tr>'
         for tokens, label in ((1_000_000, "1M input / 1M output"),
                               (10_000_000, "10M / 10M"),
                               (100_000_000, "100M / 100M")))}
</tbody></table></div>
"""
    title = f"{model['family']} pricing — per-1M-token cost across {model['provider_count']} providers"
    desc = (f"{model['family']} API pricing: {money(model['in_min'])}/1M input to "
            f"{money(model['in_max'])}/1M across {model['provider_count']} providers. "
            "Cheapest provider, output price, cache pricing and context window.")
    # A page with a single price point has nothing to compare — keep it crawlable
    # for its links, but out of the index so the site is not 1,000 thin pages.
    robots = ('<meta name="robots" content="noindex,follow">'
              if model["provider_count"] < 2 else
              '<meta name="robots" content="index,follow">')
    body += related_html(model, related, cfg)
    return (base_head(cfg, title, desc, f"{cfg['base_url']}m/{model['slug']}.html", robots)
            + body + base_foot(cfg))


def render_providers(providers, stats, cfg):
    rows = []
    for p in providers:
        pid = slugify(p["id"])
        rows.append(
            f'<tr data-name="{esc(p["id"])}">'
            f'<td><a href="{cfg["asset_prefix"]}p/{pid}.html">{esc(p["id"])}</a></td>'
            f'<td class="num" data-v="{p["families"]}">{p["families"]:,}</td>'
            f'<td class="num" data-v="{p["offers"]}">{p["offers"]:,}</td>'
            "</tr>"
        )
    body = f"""<h1>Providers</h1>
<p class="lede">{stats['providers']} distinct providers appear in the dataset. The list is
dominated by resellers and inference hosts — most of them sell models they did not train.</p>
{stat_block([(str(stats["providers"]), "providers"), (f"{stats['price_points']:,}", "price points")])}
<div class="tablewrap"><table>
<thead><tr><th data-sort>Provider</th><th class="num" data-sort>Model families</th><th class="num" data-sort>Price points</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
"""
    return (base_head(cfg, "LLM API providers — who sells what, and how much",
                      f"All {stats['providers']} providers in the LLM price index, with model counts.",
                      f"{cfg['base_url']}providers.html")
            + body + base_foot(cfg))


def render_provider_page(provider, models, cfg):
    mine = [m for m in models if any(o["provider"] == provider["id"] for o in m["offers"])]
    rows = []
    for m in sorted(mine, key=lambda x: x["family"]):
        offers = [o for o in m["offers"] if o["provider"] == provider["id"]]
        for offer in offers:
            ratio = "—"
            if offer["input"] and m["in_min"]:
                ratio = f"{offer['input'] / m['in_min']:.1f}×"
            rows.append(
                f'<tr data-name="{esc(m["family"])}">'
                f'<td><a href="{cfg["asset_prefix"]}m/{m["slug"]}.html">{esc(m["family"])}</a></td>'
                f'<td class="num" data-v="{offer["input"] if offer["input"] is not None else ""}">{money(offer["input"])}</td>'
                f'<td class="num" data-v="{offer["output"] if offer["output"] is not None else ""}">{money(offer["output"])}</td>'
                f'<td class="num" data-v="{m["in_min"] if m["in_min"] is not None else ""}">{money(m["in_min"])}</td>'
                f'<td class="num"><span class="badge-spread">{ratio}</span></td>'
                "</tr>"
            )
    body = f"""<p class="crumbs"><a href="{cfg['asset_prefix']}providers.html">Providers</a> / {esc(provider['id'])}</p>
<h1>{esc(provider['id'])}</h1>
<p class="lede">{provider['families']:,} model families, {provider['offers']:,} price points in the dataset.</p>
<p class="note">"vs cheapest" compares this provider's input price against the cheapest price
available for the same model anywhere in the index.</p>
<div class="tablewrap"><table>
<thead><tr><th data-sort>Model</th><th class="num" data-sort>Input /1M</th>
<th class="num" data-sort>Output /1M</th><th class="num" data-sort>Cheapest in</th><th class="num" data-sort>vs cheapest</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
"""
    return (base_head(cfg, f"{provider['id']} model prices — {provider['families']} models",
                      f"{provider['id']} pricing across {provider['families']} model families.",
                      f"{cfg['base_url']}p/{slugify(provider['id'])}.html")
            + body + base_foot(cfg))


def render_compare(models, cfg):
    options = []
    for m in models:
        if m["mode"] != "chat" or m["in_min"] is None:
            continue
        label = (f"{m['family']} — {money(m['in_min'])} in / {money(m['out_min'])} out"
                 f" ({m['provider_count']} provider{'s' if m['provider_count'] != 1 else ''})")
        value = f"{m['in_min']}|{m['out_min'] or 0}|{m['family']}"
        options.append(f'<option value="{esc(value)}">{esc(label)}</option>')
    body = f"""<h1>Cost calculator</h1>
<p class="lede">Pick a model, enter your token volumes, and see the bill. Prices are the
cheapest available across all providers.</p>
<div id="compare">
<div class="grid2">
<div><label class="field" for="cmp-model">Model</label>
<select id="cmp-model">{''.join(options)}</select></div>
<div><label class="field" for="cmp-in">Input tokens per request</label>
<input id="cmp-in" type="number" min="0" step="100" value="2000"></div>
<div><label class="field" for="cmp-out">Output tokens per request</label>
<input id="cmp-out" type="number" min="0" step="100" value="500"></div>
</div>
<div id="compare-out"></div>
</div>
<h2>How the maths works</h2>
<p class="note">cost = (input_tokens ÷ 1,000,000 × input_price) + (output_tokens ÷ 1,000,000 × output_price).
Vendors quote prices per million tokens, so a request with 2,000 input and 500 output tokens on a
$3/1M model costs 0.0075 USD.</p>
"""
    return (base_head(cfg, "LLM API cost calculator", "Estimate monthly LLM API cost from token volumes and per-million prices.",
                      f"{cfg['base_url']}compare.html")
            + body + base_foot(cfg))


def render_sitemap(models, providers, cfg):
    urls = ["index.html", "providers.html", "compare.html"]
    # Only pages with something to compare are worth indexing.
    urls += [f'm/{m["slug"]}.html' for m in models if m["provider_count"] > 1]
    urls += [f'p/{slugify(p["id"])}.html' for p in providers if p["families"] >= 3]
    entries = "".join(
        f"<url><loc>{cfg['base_url']}{u}</loc></url>" for u in urls
    )
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"{entries}</urlset>")
