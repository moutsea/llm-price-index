# LLM Price Index

An open, machine-readable index of what language models cost — normalized so that
**the same model can be compared across every provider that sells it**.

Most price pages show one vendor's list price. This one shows the spread: for
hundreds of model families the cheapest and the most expensive provider are
selling *the same weights* at prices that differ by an order of magnitude.

- **Data**: [`data/prices.json`](data/prices.json) · [`data/prices.csv`](data/prices.csv)
- **Site**: https://moutsea.github.io/llm-price-index/
- **Rebuilt**: daily by GitHub Actions
- **Source**: [LiteLLM](https://github.com/BerriAI/litellm)'s
  [`model_prices_and_context_window.json`](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json) (MIT)

<!-- BEGIN DATA -->
_Last rebuilt: 2026-10-22 15:56 UTC_

| | |
|---|---|
| Price points | **2,893** |
| Model families | **1,465** (1,232 chat) |
| Providers | **108** |
| Comparable across providers | **380** |
| Median price spread | **1.3×** |
| Widest spread | **60.0×** |

### Widest spreads: the same model, different prices

| Model | Vendor | Sellers | Cheapest input /1M | Priciest input /1M | Spread |
|---|---|---:|---:|---:|---:|
| [deepseek-v4.1-flash-fast](https://moutsea.github.io/llm-price-index/m/deepseek-v4-1-flash-fast.html) | DeepSeek | 2 | $0.010 | $0.600 | **60.0×** |
| [qwen3.5-9b](https://moutsea.github.io/llm-price-index/m/qwen3-5-9b.html) | Alibaba | 3 | $0.100 | $5.00 | **50.0×** |
| [llama-3.2-11b-vision-instruct](https://moutsea.github.io/llm-price-index/m/llama-3-2-11b-vision-instruct.html) | Meta | 4 | $0.049 | $2.00 | **41.2×** |
| [deepseek-v4.1-flash](https://moutsea.github.io/llm-price-index/m/deepseek-v4-1-flash.html) | DeepSeek | 12 | $0.010 | $0.400 | **40.0×** |
| [llama-3.1-8b-instruct](https://moutsea.github.io/llm-price-index/m/llama-3-1-8b-instruct.html) | Meta | 6 | $0.020 | $0.720 | **36.0×** |
| [qwen3-235b-a22b-instruct-2507](https://moutsea.github.io/llm-price-index/m/qwen3-235b-a22b-instruct-2507.html) | Alibaba | 7 | $0.090 | $3.00 | **33.3×** |
| [gpt-oss-120b](https://moutsea.github.io/llm-price-index/m/gpt-oss-120b.html) | OpenAI | 23 | $0.030 | $0.800 | **26.7×** |
| [llama-guard-3-8b](https://moutsea.github.io/llm-price-index/m/llama-guard-3-8b.html) | Meta | 5 | $0.020 | $0.484 | **24.2×** |
| [deepseek-r1-distill-qwen-14b](https://moutsea.github.io/llm-price-index/m/deepseek-r1-distill-qwen-14b.html) | DeepSeek | 4 | $0.070 | $1.60 | **22.9×** |
| [meta-llama-3.1-70b-instruct](https://moutsea.github.io/llm-price-index/m/meta-llama-3-1-70b-instruct.html) | Meta | 5 | $0.120 | $2.68 | **22.3×** |
| [mistral-small-24b-instruct-2501](https://moutsea.github.io/llm-price-index/m/mistral-small-24b-instruct-2501.html) | Mistral | 3 | $0.050 | $0.900 | **18.0×** |
| [mistral-large](https://moutsea.github.io/llm-price-index/m/mistral-large.html) | Mistral | 6 | $0.500 | $8.00 | **16.0×** |
| [mistral-nemo-instruct-2407](https://moutsea.github.io/llm-price-index/m/mistral-nemo-instruct-2407.html) | Mistral | 5 | $0.019 | $0.300 | **15.8×** |
| [deepseek-r1-0528](https://moutsea.github.io/llm-price-index/m/deepseek-r1-0528.html) | DeepSeek | 8 | $0.200 | $3.00 | **15.0×** |
| [qwen2.5-coder-32b-instruct](https://moutsea.github.io/llm-price-index/m/qwen2-5-coder-32b-instruct.html) | Alibaba | 5 | $0.060 | $0.870 | **14.5×** |
<!-- END DATA -->

## Why this exists

A model's sticker price is not a fact — it is a per-seller number. The same
weights are repackaged by first-party APIs, cloud marketplaces, and a long tail
of inference hosts. Some of those sellers are cheaper for real reasons (smaller
margin, cheaper hardware, batching). Some are cheaper for reasons that will bite
you later, and some are more expensive for no reason at all.

You cannot see any of that from a single vendor's pricing page. You can see it
here.

## Use the data

```bash
# everything, normalized
curl -O https://raw.githubusercontent.com/moutsea/llm-price-index/main/data/prices.csv

# or in Python
import json, urllib.request
data = json.load(urllib.request.urlopen(
    "https://raw.githubusercontent.com/moutsea/llm-price-index/main/data/prices.json"))
for model in data["models"]:
    if model["spread"] and model["spread"] > 5:
        print(model["family"], model["in_min"], "→", model["in_max"])
```

### Schema

`data/prices.csv`

| column | meaning |
|---|---|
| `model_id` | canonical model family, provider-independent |
| `vendor` | who trained the model (`anthropic`, `openai`, `meta`, …) |
| `mode` | `chat`, `embedding`, `image_generation`, … |
| `provider` | who is selling it |
| `input_per_1m` | USD per 1M input tokens |
| `output_per_1m` | USD per 1M output tokens |
| `cache_read_per_1m` | USD per 1M cached input tokens read |
| `cache_write_per_1m` | USD per 1M tokens written to cache |
| `context` | max input tokens |
| `free` | published at $0.00 |
| `source_model_id` | the exact upstream key, so you can verify any row |

`data/prices.json` is the same data grouped by model family, with per-model
min/max/spread and a `first_party` reference price where the vendor sells
directly.

## How normalization works

Raw keys are provider-specific (`vertex_ai-anthropic_models/claude-opus-4-7@20260101`,
`fireworks_ai/accounts/fireworks/models/deepseek-r1`, `azure/eu/gpt-4o-2024-08-06`).
[`scripts/normalize.py`](scripts/normalize.py) strips provider path segments,
date stamps and version suffixes to recover the underlying model family, then
groups every price point under it.

This is deliberately conservative: when two names cannot be proven to be the
same model, they are kept apart. Every row keeps its `source_model_id`, so you
can always audit a grouping decision yourself.

## Caveats — read these

- **Reported, not billed.** Prices come from the upstream map. Providers change
  them without notice; a row can be wrong or stale. Verify before you commit money.
- **List price only.** Batch discounts, committed-use pricing, volume deals and
  credits are not included. Real invoices are often lower.
- **Not all sellers are equal.** A cheap row is a price, not a recommendation.
  Some resellers are fine; some are unlicensed and may disappear mid-project.
- **Grouping is heuristic.** Model families can be over- or under-merged;
  open an issue if you spot one.

## Run it yourself

```bash
python3 scripts/build.py            # fetch, normalize, write data/, build dist/
python3 scripts/build.py --offline  # reuse data/raw.json
python3 -m http.server -d dist 8000 # preview the site
```

No dependencies. Python 3.9+.

## Contributing

Grouping fixes, new providers in the vendor table, and schema improvements are
all welcome. Please include the `source_model_id` you are working from, so a
change can be checked against upstream.

## License

Code: MIT. Data: derived from LiteLLM (MIT, © 2023 Berri AI) — see
[ATTRIBUTION.md](ATTRIBUTION.md).
