# Figure 5: Regime-Conditioned Performance Heatmap

## Purpose
Show that visual reasoning's value depends on market regime.
Goes in Section 4.4.

## Drawing Prompt

Create a heatmap or grouped comparison chart:

### Option A: Heatmap
- Rows: Market regimes (Trending Up, Trending Down, Ranging, Volatile, Event-Heavy)
- Columns: System configurations (Full, No Visual, Single Agent, Numerical Only)
- Cell values: Sharpe Ratio
- Color scale: diverging (red-white-green) centered at 0
- Annotations: cell values + delta from Full system

### Option B: Grouped Bar with Regime Facets
- 4-5 small bar charts, one per regime
- Each showing Full vs No-Visual performance
- Delta clearly labeled
- Shared y-axis scale for comparability

### Style
- Cool, academic color palette
- Clear regime labels with brief descriptions
- Highlight cells/bars where visual reasoning adds most value
- Should emphasize: "Visual reasoning matters most during volatile/trending regimes"
- Half-width figure (~3.25 inches)

### Key Annotation
- Star or highlight on the regime where visual reasoning adds most value
- Brief text caption explaining the pattern
