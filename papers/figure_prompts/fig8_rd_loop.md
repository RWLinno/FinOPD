# Figure 8: Closed-Loop R&D Workflow

## Purpose
Illustrate the iterative refinement process (Section 3.5).
Smaller supplementary figure showing how the system improves over iterations.

## Drawing Prompt

Create a circular/spiral workflow diagram:

### Stages (clockwise)
1. **Hypothesis** — "Trendline breaks in volatile regimes are more predictive"
   (lightbulb icon)
2. **Configure** — Adjust chart geometry weights, agent parameters
   (gear icon)
3. **Experiment** — Run backtest on validation period
   (flask icon)
4. **Evaluate** — Compute Sharpe, IC, regime-conditioned metrics
   (chart icon)
5. **Reflect** — Analyze which patterns worked, update trace
   (mirror icon)

### Visual
- Circular arrows connecting all 5 stages
- "Trace" in the center (database icon) accumulating results
- Show 2-3 iterations getting progressively better (spiral outward or improving metrics)
- Small metric callouts: "Iter 1: Sharpe 0.82", "Iter 2: Sharpe 1.05", "Iter 3: Sharpe 1.21"

### Style
- Clean, diagrammatic, minimal icons
- Teal/blue palette
- Quarter or third-width figure (compact)
- Should suggest continuous improvement without implying guaranteed convergence
