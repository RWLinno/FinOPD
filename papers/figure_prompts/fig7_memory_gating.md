# Figure 7: Memory Gating Visualization

## Purpose
Show how the gated cross-attention memory mechanism works in practice.
Goes in Section 3.4 or 4.5.

## Drawing Prompt

Create a visualization showing memory gating weights over time:

### Option A: Heatmap over decisions
- X-axis: Decision dates (subset of ~30 dates)
- Y-axis: Agent names (ChartAnalyst, PatternReasoner, EventAnalyst, RiskController)
- Cell color: Gating weight (how much each agent influenced shared memory)
- Color scale: white (0) to dark teal (1.0)
- Show decision outcome (green/red marker on top) for profit/loss

### Option B: Single-decision deep dive
- For one representative decision:
  - Show the shared memory state at each stage (5 panels)
  - Color-coded confidence values
  - Gating weight indicated by arrow thickness
  - Final memory state highlighted

### Style
- Clean, minimal, academic
- Agent-colored row labels matching architecture diagram
- Annotate a few interesting cases: "High RiskController gating → avoided loss"
- Half or full width

### Key Message
The gating mechanism learns to weight high-confidence agents more heavily,
and RiskController's influence increases during volatile periods.
