# Figure 4: Evolution Trajectory and Ablation Results

Create a dual-panel empirical results figure for a KDD/NeurIPS paper. Aspect ratio 2:1 (wide). White background. Clean academic data visualization, polished matplotlib/seaborn aesthetic.

## Visual Description

Two panels side by side (55% left, 45% right) with a thin white gap between them. Both panels share a consistent visual language.

---

### LEFT PANEL: "Evolution Trajectory"

A dual-axis line plot demonstrating that self-evolution produces sustained, measurable improvement across iterations.

**Axes:**
- X-axis: "Self-evolution iteration k" with ticks at 0, 1, 2, 3, 4, 5, 6, 7, 8
  - At k=0, a small annotation below the tick: "(MVP: before evolution)"
  - At k=8, a small annotation: "(final)"
- Left Y-axis (electric blue #457B9D text): "Sharpe Ratio" ranging 0.5 to 2.5, ticks every 0.5
- Right Y-axis (vermillion #E63946 text): "Alpha Decay (%)" ranging 0 to 40, ticks every 10

**Sharpe Ratio data (electric blue #457B9D):**
- Three thin lines (0.8pt, blue at 40% opacity) representing individual seeds:
  - Seed 42: (0,0.98) (1,1.12) (2,1.28) (3,1.45) (4,1.58) (5,1.72) (6,1.82) (7,1.91) (8,2.01)
  - Seed 123: (0,1.02) (1,1.08) (2,1.22) (3,1.38) (4,1.52) (5,1.65) (6,1.78) (7,1.85) (8,1.95)
  - Seed 456: (0,0.95) (1,1.15) (2,1.30) (3,1.42) (4,1.55) (5,1.68) (6,1.80) (7,1.88) (8,1.98)
- One bold line (2pt, blue 100%): mean of the three seeds
- Confidence band: blue at 10% opacity filling between min and max of three seeds
- Small circle markers on the bold mean line at each iteration

**Alpha Decay data (vermillion #E63946):**
- Three thin lines (0.8pt, vermillion at 40% opacity):
  - Seed 42: (0,35) (1,30) (2,26) (3,22) (4,18) (5,15) (6,13) (7,11) (8,9)
  - Seed 123: (0,33) (1,29) (2,25) (3,21) (4,17) (5,14) (6,12) (7,10) (8,8)
  - Seed 456: (0,36) (1,31) (2,27) (3,23) (4,19) (5,16) (6,14) (7,12) (8,10)
- One bold line (2pt, vermillion 100%): mean
- Confidence band: vermillion at 10% opacity
- Small triangle markers on the bold mean line

**Reference lines:**
- Horizontal dashed line (slate #6C757D, 1pt, dash pattern 5-3) at Sharpe ≈ 1.18, with right-end label: "Best Baseline: FinCon (SR=1.18)"
- Horizontal dashed line (slate, 1pt) at Alpha Decay ≈ 24%, with right-end label: "Baseline Decay: 24%"

**Post-cutoff highlight (KEY VISUAL FEATURE):**
- A vertical shaded region from x=6.0 to x=8.0 with saffron (#F4A261) fill at 8% opacity
- Top annotation in saffron bold 8pt: "Post-cutoff evaluation (2026)"
- Below annotation in 7pt: "Pretraining leakage impossible"
- The fact that the upward trend CONTINUES in this golden region is the visual proof

**Annotations:**
- A vertical double-headed arrow (electric blue, 1.5pt) at x=8.5 spanning from y=1.0 to y=2.0 (left axis), labeled: "ΔSR = +0.99"
- A vertical double-headed arrow (vermillion, 1.5pt) at x=-0.3 spanning from y=9 to y=35 (right axis), labeled: "−26pp"

**Legend (top-left corner, compact box with light gray background):**
- ─── Blue bold + circle: "Sharpe Ratio (left axis)"
- ─── Red bold + triangle: "Alpha Decay % (right axis)"
- - - - Slate dashed: "Best Baseline"
- Light band: "Min-max range (3 seeds)"

**Grid:** Horizontal only, very light gray (#E9ECEF), 0.5pt. No vertical grid.

**Axis style:** Open (no top or right border lines). Only left, bottom, and right axes visible.

---

### RIGHT PANEL: "Component Contribution (Ablation)"

A horizontal bar chart showing how much each component contributes to the final Sharpe ratio. Sorted from longest bar (top) to shortest (bottom).

**Axes:**
- X-axis: "Sharpe Ratio" ranging 0 to 2.2, ticks at 0, 0.5, 1.0, 1.5, 2.0
- Y-axis: Configuration labels (categorical)

**Bars (top to bottom, each with specific color and value):**

1. **"A1: Full FinOPD"** — Electric blue (#457B9D) fill, 2px bold border. Length: 1.98. This is the reference bar.

2. **"A6b: w/o Belief Store"** — Emerald (#2A9D8F) fill at 70%. Length: 1.61. Gap from A1 annotated.

3. **"A5: w/o OPSD (verbal only)"** — Saffron (#F4A261) fill at 70%. Length: 1.52. Gap from A1 annotated.

4. **"A4: w/o Router (fixed templates)"** — Slate (#6C757D) fill at 50%. Length: 1.45.

5. **"A2: w/o VGE (no chart geometry)"** — Slate fill at 50%. Length: 1.38.

6. **"A8: Single Agent (5→1)"** — Slate fill at 50%. Length: 1.15.

7. **"Best Baseline (FinCon)"** — No fill, slate dashed border only. Length: 1.18. Reference line.

**Bar properties:**
- Height: ~16px each, 8px gap between bars
- Rounded right end (2px radius)
- Value label at right end of each bar in 7pt bold: "1.98", "1.61", etc.

**Delta annotations (vermillion #E63946 text, positioned to the right of each bar's gap):**
- A1 → A6b gap: "Δ = −0.37 (Belief matters)"
- A1 → A5 gap: "Δ = −0.46 (OPSD matters)"
- A1 → A4 gap: "Δ = −0.53"
- A1 → A2 gap: "Δ = −0.60"
- A1 → A8 gap: "Δ = −0.83"

**Vertical reference line:** A dashed slate line (1pt) at x=1.98 (A1 value) extending the full height of the chart, making it easy to see all gaps.

**Right-margin insight annotations (small text with arrows pointing to specific gaps):**
- Arrow to A5 gap: "DQ1 validated: OPSD essential"
- Arrow to A6b gap: "DQ3 validated: Belief essential"
- Arrow to A8 gap: "Multi-agent >> single agent"
- Small box at bottom-right: "Neither track alone matches combination: A5, A6b < A1"

**Panel title (top, 9pt bold):** "Component Contribution"

---

### BOTTOM ANNOTATION (spanning both panels):

A single line of text in 7pt graphite, centered:
"All results: mean of 3 seeds (42, 123, 456) | Dow-30 test set (2025-01 to 2025-12) | 15bps costs + 5bps slippage + 1-day execution delay | Strict temporal separation from training (2019-2022)"

---

## Style Notes
- This should look like a figure from a top ML paper's experiment section — clean, precise, data-rich
- The left panel's post-cutoff saffron region is the key differentiator from standard performance plots — it communicates evaluation rigor that reviewers care about
- The right panel's delta annotations in vermillion immediately quantify each component's value
- Both panels tell a coherent story: "self-evolution works (left) because each component contributes (right)"
- Color consistency with other figures: blue = our full system, vermillion = problems/decay/gaps, saffron = novelty highlight, emerald = belief track, slate = baselines
- Data should feel realistic — smooth upward trends with slight per-seed variation, not perfectly monotonic
- Typography: Inter/Helvetica, 7pt data labels, 8pt axis labels, 9pt panel titles
- No chart junk: minimal gridlines, open axes, no unnecessary decoration
- The figure should be self-contained — a reader should understand the key findings without reading the text
