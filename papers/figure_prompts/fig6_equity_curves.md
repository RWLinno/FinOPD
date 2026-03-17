# Figure 6: Cumulative Return Curves

## Purpose
Show portfolio performance over time for key configurations.
Goes in Section 4.2 (Main Results).

## Drawing Prompt

Create a multi-line cumulative return chart:

### Lines to Show
1. **FinVL-MAS (Full)** — bold teal line, thicker (2pt)
2. **No Visual (A2)** — dashed gray line
3. **Single Agent VLM** — dotted orange line
4. **PatchTST Baseline** — thin blue line
5. **Buy-and-Hold** — thin black line

### X-axis
- Date range covering the test period (e.g., 2017-01 to 2020-12)
- Monthly tick marks

### Y-axis
- Cumulative return (starting from 1.0 or $1M)
- Both linear and optional log scale

### Annotations
- Shade drawdown periods for FinVL-MAS (light red fill)
- Mark key events (e.g., COVID crash, trade war) with vertical dashed lines
- Show final return values at right edge
- Sharpe ratio in legend for each line

### Style
- White background with light gray gridlines
- Legend in upper-left corner, ordered by final return
- Confidence bands (10th-90th percentile) as shaded area around main line if available
- Full-width figure
- Publication-quality, 300 DPI

### Key Message
FinVL-MAS outperforms across the full period, with the gap widening during volatile/trending markets.
