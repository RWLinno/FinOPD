# Figure 3: Agent Reasoning Trace Example

## Purpose
Show how the 5-agent pipeline produces an actual decision, step by step.
Goes in Section 4.5 (Qualitative Analysis) to demonstrate interpretability.

## Drawing Prompt

Create a sequential reasoning trace diagram:

### Layout
- Vertical flow, top to bottom, 5 stages
- Each stage is a "card" with the agent name, key findings, and confidence
- Arrows connect cards, with the shared memory shown as a side panel

### Content (use a realistic example)

**Card 1: ChartAnalyst** (teal border)
- Input: [small chart thumbnail]
- Findings: "Ascending triangle forming; price testing resistance at $152; 
  strong support at $145 (5 touches); bullish engulfing on last candle"
- Confidence: 0.82
- Written to Memory: chart_geometry, chart_bias="bullish"

**Card 2: PatternReasoner** (blue border)
- Input: Chart geometry from memory
- Findings: "Ascending triangle has 68% historical breakout rate;
  bullish engulfing at support confirms. However, triangle apex approaching —
  breakout should occur within 3 sessions or pattern invalidates."
- Confidence: 0.71
- Written to Memory: pattern_bias="bullish", expected_breakout="3 sessions"

**Card 3: EventAnalyst** (purple border)
- Input: Event feed, fundamentals
- Findings: "Earnings report in 5 days; sector momentum positive; 
  no material news events."
- Confidence: 0.45 (low — limited event data)
- Written to Memory: event_bias="neutral/bullish"

**Card 4: RiskController** (red border)
- Input: All prior analyses from memory
- Findings: "Current volatility: 75th percentile; R:R ratio 2.3:1;
  Stop-loss at $144.50 (below support); Max position: 3% of portfolio."
- ⚠️ Flag: "Earnings in 5 days adds event risk"
- Confidence: 0.68
- Written to Memory: risk_level="moderate", position_limit=3%

**Card 5: DecisionPM** (gold border)
- Input: Full shared memory
- Decision: **BUY** | Conviction: Moderate | Position: 2.5%
- Rationale: "Ascending triangle with bullish confirmation warrants entry.
  Reduced position (2.5% vs 3% limit) due to upcoming earnings risk.
  Stop-loss at $144.50."
- Resolved contradiction: "EventAnalyst's low confidence lowers conviction
  but does not override technical setup."
- Confidence: 0.65

### Shared Memory Panel (right side)
- Show memory state evolving as each agent writes
- Highlight confidence values and the disagreement flag

### Style
- Clean card layout with subtle shadows
- Agent icons in corner of each card
- Confidence shown as colored progress bar
- Decision card has a highlight border
- Would work as a 2/3-width or full-width figure
