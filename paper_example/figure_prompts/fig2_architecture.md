# Figure 2: System Architecture

Create a professional full-width system architecture diagram for a KDD/NeurIPS paper. Aspect ratio 2:1. White background. Flat vector, information-dense, publication-ready.

## Visual Description

The figure shows the complete FinOPD system as a left-to-right pipeline (upper portion) with a prominent dual-track feedback loop (lower portion). Every module contains specific internal details from the paper.

---

### UPPER PORTION (60% height): Main Data Flow Pipeline

Five major modules connected by thick graphite (#264653) arrows flowing left to right. Each module is a rounded rectangle with a colored header bar and detailed internal content.

---

**Module 1: "Multimodal Input" (leftmost, ~12% width)**

Header bar: graphite, label "Input o_t"

Internal content (stacked vertically with small gaps):
- A miniature candlestick chart (8-10 candles, mix of green/red, with thin wicks and a visible uptrend) labeled "60-day OHLCV Chart"
- A small newspaper clipping icon with visible headline text "AAPL beats Q3..." labeled "News & Filings (Reuters, SEC EDGAR)"
- A tiny data table showing 3 rows × 4 columns of numbers labeled "Feature Matrix x_t ∈ R^{N×F}"

Below the box: "25 Dow-30 + 10-15 CSI-300 assets"

---

**Module 2: "Visual-Geometric Encoder" (~22% width)**

Header bar: electric blue (#457B9D), label "VGE: Qwen2.5-VL-7B + LoRA (r=16)"

Internal content shows a transformation process:

Left side of the box: A small candlestick chart (~20 candles) with geometric annotations drawn ON the chart:
- A green dashed ascending trendline connecting 3 lows (labeled "slope=+0.12, R²=0.94")
- A horizontal blue band at a price level (labeled "Resistance: $152.3, 4 touches")
- A small orange circle around two candles (labeled "Bullish Engulfing")
- A dotted triangle outline (labeled "Ascending Triangle")
- A highlighted volume bar in green (labeled "Vol Divergence")

Center: A large arrow labeled "Extract & Structure"

Right side of the box: A code block showing the output JSON:
```json
{
  "trend_lines": [{"slope": 0.12}],
  "price_levels": [{"$152.3", "touches": 4}],
  "patterns": ["bullish_engulfing"],
  "formations": ["ascending_triangle"],
  "regime": "trending"
}
```

Two output ports at the bottom of the box:
- Right port: arrow going right, labeled "ChartGeometry JSON → Agents"
- Bottom port: arrow going down, labeled "Embedding g ∈ R^d → Router & Belief"

Small badges: "50K training charts" | "98% schema compliance" | "reject sampling"

---

**Module 3: "Geometry-Conditioned Factor Router" (~18% width)**

Header bar: electric blue (#457B9D), label "Factor Router: Gumbel-Softmax Top-k"

Internal content:

Top section — Input visualization:
- Two small inputs merging: "Embedding g" (from VGE) + "Regime one-hot r" (a small colored indicator showing "Trending")
- Arrow into: "MLP₁ → ReLU → MLP₂ → Logits ℓ ∈ R^160"

Middle section — Factor library visualization (the distinctive visual element):
- A grid of small dots organized into 7 labeled columns representing factor categories:
  - "K-line" (23 dots) | "Momentum" (28 dots) | "Volatility" (22 dots) | "Volume" (20 dots) | "Geometry" (25 dots) | "Quantile" (24 dots) | "Correlation" (18 dots)
- Total ~160 dots, most in light gray
- 15 dots highlighted in saffron (#F4A261) — scattered across categories but with more in Momentum and Geometry columns (showing learned preference)
- A small temperature annotation: "τ: 1.0 → 0.5 (annealed)"

Bottom section — Output:
- "Active Factor Set F_t: 15 selected factors"
- Example factors listed tiny: "RESI_ZSCORE (IR=3.04), KMID2_WMA_MOM (IR=2.20), SWING_POINT_MOMENTUM (IR=2.56)..."

Small badge: "Optimized via GRPO-lite"

---

**Module 4: "Multi-Agent Collaboration" (~28% width, largest module)**

Header bar: slate blue (#5B7B9A), label "5 Specialist Agents + Gated Shared Memory"

Internal content — Hub-and-spoke layout:

**Central hub:** A rounded rectangle in the center labeled "Gated Shared Memory" with internal details:
- "Short-term: current geometry + factor evidence + belief priors"
- "Read gates: selective attention per agent"
- "Write gates: confidence-weighted updates"
- Small lock icon indicating gating mechanism

**Five agent cards** arranged in a semicircle around the hub (each card is a small rounded rect with an icon, name, role description, and example output):

1. **ChartAnalyst (CA)** — Icon: chart-line. Role: "Geometric pattern interpretation". Example output in tiny text: "Ascending triangle forming, resistance at $152, support tested 4×, bullish bias 0.82"

2. **PatternReasoner (PR)** — Icon: magnifying-glass. Role: "Cross-pattern logical inference". Example: "Triangle + engulfing at support + volume divergence → high-probability breakout"

3. **EventAnalyst (EA)** — Icon: newspaper. Role: "News-geometry alignment". Example: "Q3 beat + sector rotation into tech aligns with bullish geometry"

4. **RiskController (RC)** — Icon: shield. Role: "Position sizing & stop-loss". Example: "Max position 2.3% given VIX=18, stop at -1.5 ATR below entry"

5. **DecisionPM (PM)** — Icon: balance-scale. Role: "Final synthesis & execution". Example: "LONG AAPL 2.3%, entry $151.5, stop $148.2, target $158"

Thin bidirectional arrows connect each agent card to the central hub.

Below the module: "Structured debate + confidence scoring + majority voting"

---

**Module 5: "Output & PnL" (rightmost, ~12% width)**

Two stacked boxes:

Top box — "Trading Decision":
- Header: graphite
- Content: "Portfolio weights w_t ∈ Δ^N" | "Position sizes s_t" | "Rationale r_t"
- Small example: "LONG AAPL 2.3%, SHORT XOM 1.1%"

Bottom box — "Risk-Adjusted PnL" (**saffron #F4A261 border, 3px, with saffron 10% fill — visual anchor**):
- A small equity curve inside (trending up)
- Metrics: "Sharpe = J(τ)" | "MDD" | "CVaR" | "Sortino"
- "Net of: 15bps + 5bps + 1-day delay"
- Star icon in corner

Arrow from top box to bottom box labeled "Execute → Realize"

---

### LOWER PORTION (40% height): Dual-Track Self-Evolution Loop

Separated from upper portion by a thin horizontal line with centered label: "Self-Evolution Loop (triggered after each rollout window of 60 trading days)"

Two parallel horizontal tracks, each in its own rounded container:

---

**Left Track: "Parametric: On-Policy Self-Distillation" (saffron #F4A261 tones)**

Container: rounded rect, saffron 1.5px border, saffron 5% fill.

Internal flow (left to right, with arrows between each step):

1. **"Hindsight PnL"** — A small box showing: "After K=20 days: Sharpe=1.82, MDD=3.2%, CVaR=-1.1%, Sortino=2.41". Label: "Privileged Information ŷ"

2. **"Teacher Conditioning"** — Shows: "Same θ + ŷ → p_T(y|o,ŷ)". A small icon of a model with a star badge.

3. **"Student Rollout"** — Shows: "Same θ, no ŷ → p_S(y|o)". A small icon of a model without badge.

4. **"Token-level JSD"** — Shows: "D_β(p_T ‖ p_S), β=0.5, KL clip c=5.0". Two small distribution bars being compared.

5. **"Shapley Credit"** — Shows: "φ_i via m=8 subset replays". Five small bars of different heights (0.31, 0.22, 0.18, 0.15, 0.14) in emerald.

6. **"LoRA Update"** — Shows: "θ ← θ - η∇(Σ φᵢ · JSD_i)". A small gradient descent icon.

**Feedback arrow:** A thick saffron dashed arrow (3px) curves upward from "LoRA Update" back to Module 2 (VGE) and Module 4 (Agents). Label on arrow: "Updates LoRA weights θ"

Additional annotations:
- "Alignment guard: KL(p_S ‖ p_ref) < ε=0.1" with a small shield icon
- "GRPO-lite for router π_R" with a small arrow to Module 3
- "Adversarial refresh every 4 iterations (COVID crash, 2022 bear)"

---

**Right Track: "Non-Parametric: Belief Consolidation" (emerald #2A9D8F tones)**

Container: rounded rect, emerald 1.5px border, emerald 5% fill.

Internal flow (left to right):

1. **"High-J Trajectories"** — Shows: "Filter: J > Q_80 (80th percentile)". A small histogram with a threshold line.

2. **"Extract Quadruples"** — Shows: "(g, F, a, J)" with labels: "geometry signature, factor set, action pattern, realized return". Four small colored circles.

3. **"FAISS Vector Index"** — Shows: a small database icon with "C_max = 10,000 entries". A small capacity bar showing ~85% full. Label: "Indexed by geometry embedding g"

4. **"Eviction Policy"** — Shows: "When full: remove lowest-J entries". A small trash icon with an arrow.

5. **"Top-5 Retrieval"** — Shows: "At inference: query current g → retrieve 5 nearest (g,F,a,J)". A small search icon with 5 result cards.

**Feedback arrow:** A thick emerald dashed arrow (3px) curves upward from "Top-5 Retrieval" back to Module 4's Shared Memory. Label on arrow: "Inject as few-shot priors"

Additional annotations:
- "Admission threshold: J ≥ Q_α, α=0.8"
- "Retrieval hit rate: 15% → 62% over iterations"

---

**Center label between two tracks:** "Complementary: parametric = slow global adaptation | belief = fast local pattern recall"

---

## Style Notes
- This is the most information-dense figure in the paper — every element corresponds to a specific detail from the method section
- The factor library dot-grid in Module 3 is a distinctive visual element that makes this figure memorable and different from generic architecture diagrams
- The agent cards with example outputs make the system feel concrete and real, not abstract
- The two feedback arrows (saffron and emerald) should be the thickest, most prominent lines in the figure
- Color discipline: blue = perception/routing, slate = agents, saffron = parametric evolution, emerald = non-parametric evolution, graphite = neutral/flow
- Icons: thin monoline stroke (Lucide/Phosphor style), 14-16px
- Typography: Inter/Helvetica, 6pt example text, 7pt sub-labels, 8pt main labels, 9pt headers
- No 3D, no gradients, no shadows, no decorative elements
- Must be legible when printed — test at 50% zoom
