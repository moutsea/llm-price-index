"""Normalize raw LiteLLM price data into a provider-agnostic model index.

The raw file is keyed by provider-specific model strings
(``vertex_ai-anthropic_models/claude-opus-4-7@20260101``,
``anthropic.claude-opus-4-20250514``, ``azure/eu/gpt-4o-2024-08-06``), so the
same underlying weights appear many times under many names at many prices.

This module reduces those keys to a canonical model family, so that the prices
actually charged for *one* model by *different* providers can be compared side
by side. That comparison is the point of the project: the spread is often an
order of magnitude.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict

# Leading tokens that identify a hosting region rather than a model.
REGION_TOKENS = {
    "global", "us", "eu", "apac", "ap", "jp", "au", "ca", "sa", "me", "af",
    "cn", "uk", "in", "us-gov", "us-gov-east-1", "us-gov-west-1", "eu-central-1",
    "us-east-1", "us-west-2",
}

# Leading dotted tokens that are vendor namespaces kept by some providers
# (bedrock writes ``anthropic.claude-...``, ``meta.llama3-...``).
VENDOR_TOKENS = {
    "anthropic", "openai", "meta", "cohere", "amazon", "mistral", "ai21",
    "stability", "deepseek", "qwen", "writer", "twelvelabs", "nvidia",
    "microsoft", "google", "zai", "moonshot", "minimax", "xiaomi", "tencent",
    "voyage", "jina", "perplexity", "snowflake", "databricks", "luma", "runway",
    "pika", "ideogram", "recraft", "bfl", "black-forest-labs", "assemblyai",
    "deepgram", "elevenlabs", "cartesia", "soniox", "sarvam", "gigachat",
}

# Dash-joined prefixes glued onto a model name (``databricks-claude-opus-4``).
DASH_PREFIXES = (
    "databricks-", "snowflake-", "openai-", "azure-", "bedrock-", "vertex-",
    "together-", "fireworks-", "deepinfra-", "replicate-", "groq-", "nim-",
    "oci-", "watsonx-", "sagemaker-", "vertex_ai-", "text-completion-",
)

# Trailing decorations that are not part of a model's identity.
# Note: ``-v0.1`` style versions are KEPT — they are different models.
# Order matters: the ``-v1:0`` qualifier has to go before the bare ``:0``,
# or the version digit is left stranded in front of the date stamp.
_TRAILING = [
    re.compile(r"-v\d+:\d+$"),          # bedrock -v1:0 qualifier
    re.compile(r":\d+$"),               # sagemaker :0
    re.compile(r"-v\d+@\w+$"),
    re.compile(r"@\d{8}$"),
    re.compile(r"@\d{4}-\d{2}-\d{2}$"),
    re.compile(r"@[a-z][a-z0-9_]*$"),   # @default, @latest, @preview
    re.compile(r"-\d{8}$"),
    re.compile(r"-\d{4}-\d{2}-\d{2}$"),
    re.compile(r"-v\d+$"),              # bedrock -v1 qualifier
    re.compile(r"-latest$"),
]

# Modes that are really the same product surface.
CHAT_LIKE = {"chat", "responses", "completion", "text-completion"}

# Which vendor made the model. Used for labelling and to locate the
# first-party price as the reference point for markup.
VENDOR_RULES = [
    ("anthropic", r"^claude"),
    ("openai", r"^(gpt|chatgpt|davinci|babbage|codex|o[1-9](-|$)|computer-use|tts-|whisper|dall-e|sora|text-embedding-ada)"),
    ("google", r"^(gemini|palm|imagen|veo|learnlm|text-bison|embedding-|gemma)"),
    ("xai", r"^grok"),
    ("deepseek", r"^deepseek"),
    ("meta", r"^(llama|meta-llama|code-llama|meta/)"),
    ("alibaba", r"^qwen"),
    ("mistral", r"^(mistral|mixtral|codestral|devstral|pixtral|magistral|voxtral|ministral)"),
    ("moonshot", r"^(kimi|moonshot)"),
    ("zhipu", r"^(glm|chatglm)"),
    ("cohere", r"^(command|embed-english|embed-multilingual|c4ai)"),
    ("amazon", r"^(nova|titan)"),
    ("microsoft", r"^phi"),
    ("ai21", r"^(jamba|j2-)"),
    ("nvidia", r"^(nemotron|llama-3\.1-nemotron)"),
    ("minimax", r"^minimax"),
    ("tencent", r"^hunyuan"),
    ("xiaomi", r"^mimo"),
]

# Providers that sell a vendor's model first-party (vendor -> provider ids).
FIRST_PARTY = {
    "anthropic": {"anthropic", "claude"},
    "openai": {"openai", "chatgpt"},
    "google": {"gemini", "vertex_ai", "vertex_ai-language-models", "vertex_ai-openai_models"},
    "xai": {"xai"},
    "deepseek": {"deepseek"},
    "mistral": {"mistral", "codestral"},
    "alibaba": {"dashscope", "qwen_ai_platform", "qwencloud"},
    "moonshot": {"moonshot"},
    "zhipu": {"zai", "zhipu"},
    "cohere": {"cohere", "cohere_chat"},
    "amazon": {"bedrock", "bedrock_converse", "amazon_nova", "sagemaker"},
    "microsoft": {"azure", "azure_ai"},
    "meta": set(),      # never sold first-party
    "ai21": {"ai21"},
    "nvidia": {"nvidia_nim"},
    "minimax": {"minimax"},
    "tencent": {"tencent"},
    "xiaomi": {"xiaomi_mimo"},
}

PRICE_FIELDS = {
    "input": "input_cost_per_token",
    "output": "output_cost_per_token",
    "cache_read": "cache_read_input_token_cost",
    "cache_write": "cache_creation_input_token_cost",
}

# Vendors whose canonical model ids use dots for sub-versions.
DOT_CONVENTION = {"openai", "google", "zhipu", "deepseek", "moonshot", "xai"}

# Cosmetic casing for well-known model families.
ACRONYMS = {
    "gpt": "GPT", "glm": "GLM", "api": "API", "llm": "LLM", "vl": "VL",
    "moe": "MoE", "omni": "Omni", "gpt4": "GPT-4", "ocr": "OCR",
    "tts": "TTS", "stt": "STT", "r1": "R1", "v3": "V3", "v2": "V2",
}


def _strip_leading_tokens(key: str) -> str:
    """Drop region and vendor namespace prefixes such as ``us.anthropic.``."""
    changed = True
    while changed:
        changed = False
        for token in REGION_TOKENS | VENDOR_TOKENS:
            prefix = token + "."
            if key.startswith(prefix):
                key = key[len(prefix):]
                changed = True
    return key


def _strip_dash_prefixes(key: str) -> str:
    changed = True
    while changed:
        changed = False
        for prefix in DASH_PREFIXES:
            if key.startswith(prefix) and len(key) > len(prefix) + 2:
                key = key[len(prefix):]
                changed = True
    return key


def canonical_key(raw_key: str) -> tuple[str, str]:
    """Reduce a provider-specific model key to ``(group_key, display_hint)``.

    ``group_key`` is lower-kebab and never contains a dot, so that
    ``gpt-5.5`` and ``gpt-5-5`` collapse together. ``display_hint`` keeps the
    original punctuation so the site can render ``GPT-5.5`` rather than
    ``gpt-5-5``.
    """
    key = raw_key.lower().strip()

    # Fine-tunes are described as ``ft:gpt-4.1:org::id``; the base model is
    # what has a comparable price across providers.
    if key.startswith("ft:"):
        key = key[3:].split(":", 1)[0]
    key = key.split(":", 1)[0] if key.count(":") and not key.endswith(tuple("0123456789")) else key

    # Provider paths: the model is always the final segment.
    if "/" in key:
        key = key.rsplit("/", 1)[-1]

    key = _strip_leading_tokens(key)
    key = _strip_dash_prefixes(key)

    # Vertex/Azure write snapshot tags as ``model@20260101``; treating "@" as a
    # separator lets the date rules below strip it and keeps non-date tags
    # (``mistral-large@2411``) distinct instead of silently merging them.
    key = key.replace("@", "-")

    for _ in range(3):
        before = key
        for pattern in _TRAILING:
            key = pattern.sub("", key)
        if key == before:
            break

    key = key.strip("-_ .")
    if not key:
        return "", ""

    # Dots between digits are version separators: normalise for grouping only.
    group = re.sub(r"(?<=\d)\.(?=\d)", "-", key)
    group = re.sub(r"[^a-z0-9.\-]+", "-", group)
    group = re.sub(r"-{2,}", "-", group).strip("-")
    return group, key


def detect_vendor(family: str) -> str:
    for vendor, pattern in VENDOR_RULES:
        if re.match(pattern, family):
            return vendor
    return "other"


def prettify(text: str) -> str:
    """A human-readable label for a family key, e.g. ``gpt-5.5`` -> ``GPT-5.5``."""
    out = []
    for part in re.split(r"[-_ ]", text):
        if not part:
            continue
        low = part.lower()
        if low in ACRONYMS:
            out.append(ACRONYMS[low])
        elif re.fullmatch(r"\d+(\.\d+)?[bBmMkK]?", part):
            out.append(part)
        elif re.fullmatch(r"[bmk]", part, re.I):
            out.append(part.upper())
        else:
            out.append(part[:1].upper() + part[1:])
    label = "-".join(out)
    # Keep decimals readable: "GPT-5-5" -> "GPT-5.5" is handled by display_hint.
    return label


def _num(value):
    """Return a float for a per-token price, or None when absent/invalid."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value < 0:
        return None
    return float(value)


def _per_million(value):
    """Convert a per-token cost to USD per 1M tokens."""
    return None if value is None else round(value * 1_000_000, 6)


def build_index(raw: dict) -> dict:
    """Turn the raw LiteLLM mapping into a normalized index of model families."""
    providers = {}
    groups = defaultdict(lambda: {
        "offers": [], "modes": Counter(), "context": None, "max_output": None,
        "displays": Counter(),
    })

    for raw_key, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        provider = entry.get("litellm_provider")
        if not provider or not isinstance(provider, str) or " " in provider:
            continue
        mode = entry.get("mode")
        if not mode or not isinstance(mode, str) or "one of:" in mode:
            continue

        prices = {name: _num(entry.get(field)) for name, field in PRICE_FIELDS.items()}
        if prices["input"] is None and prices["output"] is None:
            continue
        is_free = prices["input"] == 0 and prices["output"] == 0

        group, display = canonical_key(raw_key)
        if not group or len(group) < 2:
            continue

        mode_key = "chat" if mode in CHAT_LIKE else mode
        key = f"{group}|{mode_key}"

        bucket = groups[key]
        bucket["modes"][mode_key] += 1
        bucket["displays"][display] += 1

        ctx = entry.get("max_input_tokens")
        if isinstance(ctx, int) and ctx > 0:
            bucket["context"] = max(bucket["context"] or 0, ctx)
        out = entry.get("max_output_tokens")
        if isinstance(out, int) and out > 0:
            bucket["max_output"] = max(bucket["max_output"] or 0, out)

        bucket["offers"].append({
            "provider": provider,
            "raw_id": raw_key,
            "input": _per_million(prices["input"]),
            "output": _per_million(prices["output"]),
            "cache_read": _per_million(prices["cache_read"]),
            "cache_write": _per_million(prices["cache_write"]),
            "free": is_free,
            "deprecated": bool(entry.get("deprecation_date")),
        })
        providers.setdefault(provider, {"id": provider, "offers": 0, "families": set()})
        providers[provider]["offers"] += 1
        providers[provider]["families"].add(key)

    models = []
    for key, bucket in groups.items():
        group, mode = key.rsplit("|", 1)
        offers = _dedupe_offers(bucket["offers"])
        if not offers:
            continue

        # Display: the spelling most providers publish. On a tie, follow the
        # vendor's own convention — OpenAI/Google/Zhipu write "gpt-5.5",
        # Anthropic/Meta/Alibaba write "claude-opus-4-5".
        vendor = detect_vendor(group)
        prefer_dots = vendor in DOT_CONVENTION
        candidates = bucket["displays"]

        def rank(item):
            text, count = item
            return (count, ("." in text) == prefer_dots, text)

        display = max(candidates.items(), key=rank)[0]

        paid_in, paid_out = _mark_outliers(offers)
        in_min, in_max = (min(paid_in), max(paid_in)) if paid_in else (None, None)
        out_min, out_max = (min(paid_out), max(paid_out)) if paid_out else (None, None)
        cache_priced = any(o["cache_read"] is not None for o in offers)
        first_party = _first_party_offer(offers, vendor)

        models.append({
            "id": group if mode == "chat" else f"{group}-{mode}",
            "family": display,
            "label": prettify(display),
            "vendor": vendor,
            "mode": mode,
            "context": bucket["context"],
            "max_output": bucket["max_output"],
            "provider_count": len({o["provider"] for o in offers}),
            "in_min": in_min, "in_max": in_max,
            "out_min": out_min, "out_max": out_max,
            "spread": round(in_max / in_min, 2) if in_min and in_max and in_min > 0 else None,
            "cache_priced": cache_priced,
            "first_party": {
                "provider": first_party["provider"],
                "input": first_party["input"],
                "output": first_party["output"],
            } if first_party else None,
            "offers": offers,
        })

    # Two entries can still land on one display name when a provider tags an
    # embedding or audio model as "chat". Disambiguate rather than silently
    # showing the same name twice with different numbers.
    seen = Counter(m["family"] for m in models)
    for model in models:
        if seen[model["family"]] > 1 and model["mode"] != "chat":
            model["family"] = f'{model["family"]} ({model["mode"].replace("_", " ")})'

    models.sort(key=lambda m: (m["mode"] != "chat", m["provider_count"] * -1, m["family"]))
    provider_list = sorted(
        ({"id": p["id"], "offers": p["offers"], "families": len(p["families"])}
         for p in providers.values()),
        key=lambda p: (-p["offers"], p["id"]),
    )
    return {"models": models, "providers": provider_list}


def _mark_outliers(offers, ratio_factor=8.0, price_factor=20.0, min_sellers=3):
    """Flag price points that do not look like the other sellers of the model.

    Comparing prices alone does not work: gpt-oss-120b is genuinely sold at
    $0.03/1M by wandb and deepinfra and at $0.15 by most others, so flagging the
    cheap ones would delete the only useful information on the page. What an
    anomaly actually breaks is the *shape* of the price — coralbricks lists
    deepseek-v4.1-flash at $0.01 input but $1.20 output, an in/out ratio 30×
    away from every other seller, and that single row was defining the site's
    headline "40× spread". So: compare each offer's in/out ratio against the
    median ratio, and separately catch prices an order of magnitude below the
    median. Outliers stay in the table with a badge but are excluded from the
    min/max statistics.
    """
    for offer in offers:
        offer["outlier"] = False

    paid = [o for o in offers if o["input"] and o["output"] and not o["free"]]
    everything = ([o["input"] for o in offers if o["input"] is not None and not o["free"]],
                  [o["output"] for o in offers if o["output"] is not None and not o["free"]])
    if len(paid) < min_sellers:
        return everything

    med_in = statistics.median([o["input"] for o in paid])
    med_ratio = statistics.median([o["input"] / o["output"] for o in paid])
    if med_in <= 0 or med_ratio <= 0:
        return everything

    for offer in paid:
        ratio = offer["input"] / offer["output"]
        shape_bad = ratio / med_ratio > ratio_factor or med_ratio / ratio > ratio_factor
        offer["outlier"] = bool(shape_bad or offer["input"] < med_in / price_factor)

    core = [o for o in paid if not o["outlier"]]
    if len(core) < 2:                   # everything looks odd — trust the raw data
        for offer in offers:
            offer["outlier"] = False
        return everything
    return [o["input"] for o in core], [o["output"] for o in core]


def _dedupe_offers(offers):
    """Collapse duplicate (provider, price) rows, preferring live ids."""
    best = {}
    for offer in offers:
        key = (offer["provider"], offer["input"], offer["output"])
        current = best.get(key)
        if current is None or (current["deprecated"] and not offer["deprecated"]):
            best[key] = offer
    return sorted(best.values(), key=lambda o: (o["input"] if o["input"] is not None else 9e9, o["provider"]))


def _first_party_offer(offers, vendor):
    """The vendor's own list price, if it sells the model directly."""
    allowed = FIRST_PARTY.get(vendor) or set()
    candidates = [o for o in offers if o["provider"] in allowed and not o["free"]]
    if not candidates:
        return None
    return min(candidates, key=lambda o: (o["input"] if o["input"] is not None else 9e9))
