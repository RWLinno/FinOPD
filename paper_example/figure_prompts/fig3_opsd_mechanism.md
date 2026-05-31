# Figure 3: On-Policy Self-Distillation Mechanism

Create a detailed mechanism diagram for a KDD/NeurIPS paper. Aspect ratio 1:1 (square). White background. Flat vector, publication-ready. This figure explains the CORE TECHNICAL CONTRIBUTION in detail.

## Visual Description

Three horizontal bands stacked vertically. Each band has rich internal content directly from the paper's equations and method description.

---

### TOP BAND (~18% height): "Why Hindsight PnL, Not Direction Labels?"

A comparison panel split into left and right halves by a thin vertical divider.

**Left half (vermillion #E63946 subtle wash, 5% opacity):**
- Header: "Standard Approach" in vermillion bold
- A small flow diagram:
  - Box: "Privileged Info = Direction Label (price ↑/↓)"
  - Arrow down
  - Box: "Teacher pushes: predict direction correctly"
  - Arrow down
  - Result box: "Accuracy: 72% → 81% ↑" in green text
  - BUT below it: "Cumulative Returns: +15% → +3% ↓↓" in vermillion bold
  - Below: "Position sizing, correlation, drawdown effects IGNORED"
- Large vermillion "✗" icon
- Label: "= Reward Hacking"
- Citation: "(Losing Winner, 2025)"

**Right half (electric blue #457B9D subtle wash, 5% opacity):**
- Header: "Our Approach" in electric blue bold
- A small flow diagram:
  - Box: "Privileged Info = Realized PnL (Sharpe, MDD, CVaR)"
  - Arrow down
  - Box: "Teacher pushes: reason in ways that WERE profitable"
  - Arrow down
  - Result box: "Optimizes risk-adjusted returns DIRECTLY"
  - Below: "Portfolio-level effects captured by construction"
- Large blue "✓" icon
- Label: "= No Hacking"

**Connecting insight (centered below both halves):** "The teacher knows HOW PROFITABLE the reasoning was, not just whether the price went up."

---

### MIDDLE BAND (~52% height): "Differential Conditioning Mechanism"

A large dashed-border rectangle spans the full width. At the top of this dashed box, a centered label in italic: "Same LoRA Model θ — identical weights, different input context (teacher frozen at θ₀)"

Inside, two parallel vertical streams (Student left, Teacher right) with a matching zone in between:

---

**LEFT STREAM: "STUDENT" (electric blue #457B9D tones)**

Container: rounded rect, blue 1.5px border, blue 6% fill.
Header: "STUDENT" in blue bold 10pt.

Input section (vertical stack of three items, each with icon + label):
- 📊 "ChartGeometry JSON" — show a tiny JSON bracket icon with fields: trend_lines, price_levels, patterns
- 📋 "Factor Evidence (15 selected)" — show a tiny table with factor names and values: "RESI_ZSCORE=1.34, KMID2_WMA=-0.82, SWING_MOM=2.1..."
- 📰 "Market Context" — show a tiny text block: "AAPL Q3 beat, Fed holds rates, VIX=18..."

Arrow down labeled "Concatenate & Forward"

Model block: rounded rect with cpu/chip icon, label "p_S(y^(i)_{t,n} | o_t, y_{<n})"

Arrow down labeled "Generate tokens"

Output — Token probability distribution visualization:
- 10 vertical bars of varying heights representing probabilities over key action tokens
- Bar labels (tiny, 6pt): "buy" "hold" "wait" "reduce" "sell" "size_2%" "size_1%" "stop_1.5ATR" "target_$158" "rationale..."
- Bar heights (approximate): 0.04, 0.06, 0.12, 0.08, 0.03, 0.25, 0.18, 0.12, 0.08, 0.04
- Bars colored in electric blue
- Label below: "p_S: uncertain, hedged distribution"

---

**RIGHT STREAM: "TEACHER" (vermillion #E63946 tones)**

Container: rounded rect, vermillion 1.5px border, vermillion 6% fill.
Header: "TEACHER (frozen θ₀)" in vermillion bold 10pt.

Input section (same three items as student, PLUS one additional prominent item):
- 📊 "ChartGeometry JSON" (same as student)
- 📋 "Factor Evidence" (same)
- 📰 "Market Context" (same)
- **⭐ THE PRIVILEGED INFORMATION BOX (saffron #F4A261, 3px border, 15% fill, THE MOST PROMINENT ELEMENT IN THE ENTIRE FIGURE):**
  - Star icon in top-left corner
  - Header: "[HINDSIGHT PRIVILEGED INFO]" in saffron bold
  - Content (each on its own line, clear and readable):
    - "Sharpe Ratio = 1.82 (over next K=20 days)"
    - "Max Drawdown = 3.2%"
    - "CVaR (95%) = -1.1%"
    - "Sortino Ratio = 2.41"
    - "Realized Return = +8.3%"
  - Footer: "Available ONLY in hindsight — student never sees this"

Arrow down labeled "Concatenate & Forward (with privileged context)"

Model block: same as student, label "p_T(y^(i)_{t,n} | o_t, y_{<n}, ŷ)"

Arrow down

Output — Token probability distribution:
- Same 10 bars but with DIFFERENT heights — more peaked/confident:
- Heights: 0.02, 0.03, 0.05, 0.04, 0.01, 0.42, 0.25, 0.10, 0.05, 0.03
- Bars colored in vermillion
- Label below: "p_T: confident, informed distribution"

---

**CENTER MATCHING ZONE (between the two streams, ~10% width):**

- A large double-headed horizontal arrow connecting the two distribution visualizations
- Center label (bold 9pt): "Token-level JSD"
- Formula below arrow: "D_β(p_T ‖ p_S) = β·KL(p_T‖m) + (1-β)·KL(p_S‖m)"
- Below formula: "m = 0.5·p_T + 0.5·p_S (β=0.5)"
- Below that: "Per-token KL clip:"
- A tiny illustration showing a single bar being "capped" — a tall bar with a horizontal line cutting across it at height c, and the portion above c is grayed out
- Label: "cap c = 5.0 (prevents stylistic tokens from dominating)"

---

### BOTTOM BAND (~30% height): "Multi-Agent Shapley Credit Assignment"

Container: rounded rect, emerald (#2A9D8F) 1.5px border, emerald 5% fill.
Header (left-aligned): "Shapley-Weighted Credit Assignment" in emerald bold.

**Left section (~30% width): "The Problem"**
- Text: "5 agents contribute unequally to each trajectory"
- Small illustration: 5 agent icons (same as architecture fig) with question marks above them
- Text: "Uniform weighting → dilutes signal from high-contributing agents"
- Text: "Solution: estimate marginal contribution via subset replay"

**Center section (~40% width): "Shapley Estimation"**
- A bar chart with 5 vertical bars in emerald, heights proportional to Shapley values:
  - CA: φ₁ = 0.31 (tallest bar)
  - PR: φ₂ = 0.22
  - EA: φ₃ = 0.18
  - RC: φ₄ = 0.15
  - PM: φ₅ = 0.14
- Each bar has the agent icon at its base and the φ value labeled on top
- X-axis: agent abbreviations
- Y-axis: "Shapley value φᵢ"
- Annotation: "m = 8 random subset replays per trajectory"
- Below the chart: "Σφᵢ = 1.0"

**Right section (~30% width): "The Effect"**
- Formula box (graphite border):
  - "Weighted Loss = Σ_n φ_{i(n)} · D_β(p_T ‖ p_S)|_n"
- Explanation:
  - "CA (φ=0.31): receives 2.2× stronger gradient"
  - "PM (φ=0.14): receives 1.0× baseline gradient"
- Small comparison:
  - "Without Shapley: all agents get equal signal → slow convergence"
  - "With Shapley: high-contributors learn faster → efficient evolution"

---

## Style Notes
- The saffron PRIVILEGED INFO box must be the single most eye-catching element — it's what makes our approach novel
- The two distribution bar charts should be clearly different (teacher more peaked) to visually communicate "the teacher is more confident because it knows the outcome"
- The Shapley bar chart should feel like a real data visualization, not a schematic
- The top motivation band establishes WHY before the middle band shows HOW
- Color discipline: blue = student, vermillion = teacher, saffron = privileged info (novelty), emerald = credit assignment
- Typography: Inter/Helvetica, 6pt tiny labels, 7pt sub-text, 8pt main labels, 9pt section headers, 10pt stream headers
- No 3D, no gradients, no shadows
- Dense but organized — clear visual hierarchy guides the eye top→middle→bottom
