# Figure 1: FinVL-MAS System Architecture

## Purpose
Main architecture diagram for Section 3.1. This is the most important figure in the paper — 
it must convey the entire system at a glance.

## Drawing Prompt

Create a professional research paper architecture diagram with these specifications:

### Layout
- Horizontal flow, left-to-right, with 4 major stages
- Clean, minimal style with rounded rectangles, directional arrows
- Color palette: teal/blue primary, orange/amber secondary, gray for infrastructure
- White or very light background, suitable for academic print

### Components (left to right)

**Stage 1 — Data & Rendering (left, teal box)**
- Input: "OHLCV Data" (cylinder icon)
- Process: "Chart Renderer" (rounded rect)
- Output: Candlestick chart thumbnail (small embedded image)
- Also show: "Technical Indicators" feeding in
- Label: "Visual Perception"

**Stage 2 — Geometry Extraction (center-left, blue box)**
- Two parallel paths:
  - Upper: "Rule-Based Detector" → trendlines, S/R, candlestick patterns
  - Lower: "VLM Analyzer" → formations, holistic interpretation
- Both feed into: "Chart Geometry" (structured data icon)
- Show fusion arrow merging both paths
- Label: "Structured Extraction"

**Stage 3 — Multi-Agent Reasoning (center, large amber/orange box)**
- 5 agent boxes arranged vertically:
  1. "ChartAnalyst" (eye icon) — receives chart geometry
  2. "PatternReasoner" (brain icon) — receives patterns
  3. "EventAnalyst" (newspaper icon) — receives events (dashed, optional)
  4. "RiskController" (shield icon) — receives all above
  5. "DecisionPM" (gavel icon) — integrates all
- Central element: "Shared Memory" (cylinder with radiating connections to all agents)
- Show "Gated Cross-Attention" label on the connections
- Confidence scores shown as small badges on connections (e.g., "0.85")
- Label: "Cognitive Decomposition"

**Stage 4 — Decision & Evaluation (right, green box)**
- "Decision Output" box with: Action, Confidence, Rationale
- Below: "Backtester" → "Metrics" (Sharpe, IC, etc.)
- Feedback arrow from Metrics back to Stage 1 (dashed, labeled "R&D Loop")
- Label: "Decision & Validation"

### Style Guidelines
- Font: sans-serif (like Inter or Helvetica), 9-10pt for labels
- Agent boxes: white fill with colored left border (each agent a different shade)
- Arrows: gray with arrowheads, labeled where important
- Shared Memory: distinctive shape (hexagon or cylinder with highlight)
- Overall: NeurIPS-quality, single-column width (~3.25 inches) or full-width (~6.5 inches)
- Must be readable at 100% zoom in a PDF

### Key Design Decisions
- Emphasize the FLOW from visual perception to decision
- Make Shared Memory visually central (the hub of communication)
- Show the cognitive decomposition clearly (5 distinct specialist roles)
- The R&D feedback loop should be visible but not dominant
- Use icons sparingly — no more than one per agent box
