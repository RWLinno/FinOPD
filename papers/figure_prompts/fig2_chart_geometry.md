# Figure 2: Chart Geometry Extraction Example

## Purpose
Show a concrete example of what "structured chart geometry" means on a real chart.
Goes in Section 3.2 to make the visual analysis contribution tangible.

## Drawing Prompt

Create a annotated financial chart figure with these specifications:

### Base Chart
- Professional candlestick chart with ~60 daily bars
- Include volume bars at bottom (shorter subplot)
- Use a real or realistic-looking stock price series
- Show clear trending, consolidation, and breakout phases
- Clean, publication-quality rendering (no gridlines clutter)

### Geometric Annotations (overlay on chart)
1. **Trendlines** (2-3):
   - One ascending support trendline (green dashed) connecting 3+ lows
   - One descending resistance trendline (red dashed) connecting 2+ highs  
   - Label each with slope angle and R² value

2. **Support/Resistance Levels** (3-4):
   - Horizontal bands (semi-transparent) at key price levels
   - Blue for support, orange for resistance
   - Label with price and touch count (e.g., "Support: $142.50 (4 touches)")

3. **Candlestick Patterns** (2-3):
   - Circle/highlight specific candle formations
   - Labels: "Bullish Engulfing", "Doji", "Hammer"
   - Small colored arrows pointing to them

4. **Chart Formation** (1):
   - Outline a visible formation (e.g., ascending triangle)
   - Dashed lines showing the formation boundaries
   - Label: "Ascending Triangle (78% breakout probability)"

5. **Volume Signal** (1):
   - Highlight a volume bar with divergence from price
   - Label: "Bearish Volume Divergence"

### Layout
- Main chart: ~70% of figure height
- Volume subplot: ~20%
- Legend/annotation key: small box in corner showing color codes
- Right side or below: Small "ChartGeometry JSON" excerpt showing structured output

### Style
- Dark chart background (#1a1b26) with light candles, or white background with standard colors
- Annotation colors should be distinct but not garish
- Font: 8-9pt sans-serif for annotations
- Full-width figure for maximum detail
- Should work in both color and grayscale

### Key Message
The figure should clearly show that our system doesn't just "look at a chart" — it extracts
precise geometric structures that can be reasoned about symbolically.
