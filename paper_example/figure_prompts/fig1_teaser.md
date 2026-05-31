# Figure 1: Teaser — Motivation and Comparison with Prior Work

Create a professional academic figure for a KDD/NeurIPS paper. Aspect ratio 2:1 (wide). White background. Flat vector, sophisticated. This figure appears in the Introduction and must immediately communicate: (1) the problem with existing systems, (2) empirical evidence of failure, and (3) how FinOPD is fundamentally different.

## Visual Description

The figure has THREE columns of roughly equal width, telling a story left to right: "What exists → Why it fails → How we fix it."

---

### LEFT COLUMN (~30% width): "Existing Paradigm: Verbal Reinforcement"

A vertical flow diagram showing how current financial multi-agent systems (TradingAgents, FinCon, FinAgent) self-improve. Rendered in muted silver-gray tones (#ADB5BD) to convey "this is the old way."

**Flow (top to bottom):**

1. A rounded box labeled "Multi-Agent Trading System" containing three small logos/labels stacked: "TradingAgents (2025)", "FinCon (NeurIPS 2024)", "FinAgent (2024)". A small team icon above.

2. Arrow down (gray)

3. A rounded box labeled "Trade Execution" with a small order ticket icon showing "BUY / SELL / HOLD"

4. Arrow down (gray)

5. A rounded box labeled "Text Reflection" with a speech bubble icon. Inside, show actual example reflection text in tiny italic font:
   - "I was too aggressive on AAPL."
   - "Should have respected the resistance."
   - "Next time, reduce position size in high-vol."

6. Arrow down (gray)

7. A rounded box labeled "Rewrite Prompt Prefix" with a pencil-on-document icon. Inside: "beliefs = [cautious, respect_resistance, ...]"

8. A curved arrow looping from box 7 back up to box 1, labeled "Next episode"

**Key annotations (vermillion #E63946, bold, placed beside the flow):**
- Beside box 5→7: "Text only — no gradient signal ✗"
- Beside the loop arrow: "Parameters unchanged ✗"
- At the bottom: "= Open-loop verbal reinforcement"

**Column header (top, centered):** "Prior Work" in slate gray, 10pt

---

### CENTER COLUMN (~35% width): "Empirical Evidence of Failure"

This column presents the HARD EVIDENCE that motivates our work. It contains two stacked mini-figures showing real findings from cited papers. Rendered in vermillion (#E63946) tones to convey "this is the problem."

**Top mini-figure (~50% of column height): "The Live Trading Gap"**

A bar chart comparing backtest vs. live performance for 3 frontier models:
- X-axis: three model groups: "GPT-4o", "Claude-3.5", "Gemini-2.0"
- Y-axis: "Cumulative Return (%)" ranging from -15% to +20%
- For each model, two bars side by side:
  - Light blue bar: "Backtest" — heights: +18%, +15%, +12% (all positive)
  - Vermillion bar: "Live (12 months)" — heights: -8%, -12%, -5% (all negative!)
- A horizontal dashed line at 0%
- Title above: "Backtest vs. Live Performance"
- Citation: "(DeepFund, 2025)"
- Key insight annotation: "ALL frontier models lose money in live trading"

**Bottom mini-figure (~50% of column height): "The Reward Hacking Trap"**

A scatter plot or dual-bar showing the paradox:
- X-axis: "Directional Accuracy (%)" ranging 60-85%
- Y-axis: "Cumulative Return (%)" ranging -15% to +20%
- Data points:
  - "Base LLM": accuracy ~68%, return ~+5% (blue dot)
  - "After RL finetuning": accuracy ~81%, return ~-3% (vermillion dot, larger)
  - An arrow from the blue dot to the vermillion dot, labeled "RL finetuning"
- The arrow goes RIGHT (higher accuracy) but DOWN (lower returns) — visually striking
- Title above: "The Reward Hacking Paradox"
- Citation: "(Losing Winner, 2025)"
- Key insight annotation: "Higher accuracy ≠ higher returns! Optimizing the wrong target."

**Column header (top, centered):** "Why It Fails" in vermillion, 10pt bold

---

### RIGHT COLUMN (~35% width): "FinOPD: Three Design Insights"

This column shows our THREE key design decisions that solve the problems shown in the center column. Rendered in vibrant colors (electric blue #457B9D, saffron #F4A261, emerald #2A9D8F).

**Three stacked insight cards, each a rounded rectangle with a colored left border (4px) and light fill:**

**Card 1 (saffron #F4A261 left border, saffron 8% fill):**
- Header: "DQ1: Privileged Info = Hindsight PnL"
- Icon: star
- Content: A small before/after comparison:
  - "Standard: Teacher sees direction label (↑/↓)" with ✗
  - "Ours: Teacher sees realized Sharpe=1.82, MDD=3.2%" with ✓
- Bottom text: "→ Anchors learning to profitability, not accuracy"
- Arrow pointing left to the "Reward Hacking" evidence: "Solves this ←"

**Card 2 (emerald #2A9D8F left border, emerald 8% fill):**
- Header: "DQ2: Shapley-Weighted Credit Assignment"
- Icon: users/team
- Content: A tiny bar chart showing 5 unequal bars (φ₁=0.31 to φ₅=0.14)
- Text: "5 agents contribute unequally → weight distillation loss by marginal contribution"
- Bottom text: "→ Prevents signal dilution across agents"

**Card 3 (electric blue #457B9D left border, blue 8% fill):**
- Header: "DQ3: Parametric + Non-Parametric Dual Track"
- Icon: git-branch (two paths)
- Content: Two small parallel arrows:
  - Saffron arrow: "OPSD → slow global θ adaptation"
  - Emerald arrow: "Belief Store → fast local pattern recall"
- Text: "Markets have both drift AND recurring patterns → need both mechanisms"
- Bottom text: "→ Neither alone is sufficient (ablation: A5, A6b < A1)"

**Below the three cards, a small result teaser:**
- A compact one-line result: "Result: SR 1.98 vs. best baseline 1.18 (+68%), sustained over 8 iterations, validated post-cutoff"
- In electric blue bold

**Column header (top, centered):** "Our Solution" in electric blue, 10pt bold

---

### CONNECTING ELEMENTS (between columns):

- A large arrow from the left column to the center column, labeled "leads to" in gray
- A large arrow from the center column to the right column, labeled "motivates" in gray
- These arrows should be subtle (gray, 1.5px) — the columns themselves tell the story

---

## Style Notes
- This figure tells a NARRATIVE: "Here's what exists → Here's proof it fails → Here's how we fix it"
- NO system architecture details here — that's Figure 2's job. This figure is purely about MOTIVATION and POSITIONING
- The center column's empirical evidence (bar chart + scatter plot) makes this figure unique — most teaser figures are abstract, ours shows DATA
- The vermillion "failure evidence" in the center should be visually alarming — it's the hook that makes reviewers care
- The right column's three cards should feel like a clean, actionable response to the problems shown
- Color narrative: gray (old) → vermillion (problem) → blue/saffron/emerald (solution)
- Typography: Inter/Helvetica, 7pt chart labels, 8pt card content, 9pt headers, 10pt column headers
- No 3D, no gradients, no shadows
- The figure should be self-explanatory — a reviewer glancing at it for 5 seconds should understand: "existing systems fail in live trading because of reward hacking; this paper fixes it with three specific design decisions"
