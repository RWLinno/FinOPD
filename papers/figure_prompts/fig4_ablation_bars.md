# Figure 4: Ablation Study Bar Chart

## Purpose
Visualize the ablation results (Table 2) as a bar chart for quick visual comparison.
Goes in Section 4.3.

## Drawing Prompt

Create a grouped bar chart:

### Data
- X-axis: 8 ablation configurations (A1-A8)
- Y-axis: Sharpe Ratio (primary), with optional secondary metric
- A1 (Full system) should be highlighted/emphasized

### Bar Labels
- A1: Full FinVL-MAS (highlighted in teal/blue)
- A2: No Visual
- A3: Raw Chart (no geometry)
- A4: Single Agent
- A5: No Gated Memory
- A6: No Events
- A7: No Risk Controller
- A8: Rule-based Only

### Style
- A1 bar in bold teal with slight glow/highlight
- Other bars in muted gray with slight color tint
- Value labels on top of each bar
- Horizontal dashed line at A1's value for easy comparison
- Delta annotations (e.g., "-12%" below bars that are worse)
- Error bars if we have multiple runs
- Clean white background, NeurIPS-compatible
- Single-column width (~3.25 inches)
- Font: 8pt sans-serif

### Key Annotations
- Arrow pointing to biggest drop with label: "Removing visual reasoning causes largest degradation"
- Group bars by category: "Visual" (A2,A3,A8), "Architecture" (A4,A5), "Context" (A6,A7)
