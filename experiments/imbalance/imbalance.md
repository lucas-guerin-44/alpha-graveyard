# Imbalance / Fair Value Gap (FVG) Strategy

**Status**: INHERITED from engine repo, not yet re-validated in research
**Verdict**: UNKNOWN — needs Phase 3-6 validation

## Thesis
Fair Value Gap (FVG) is a 3-bar price-action pattern where bar N+1's low exceeds bar N-1's high (bullish FVG) or bar N+1's high is below bar N-1's low (bearish FVG). The gap represents an imbalance that price often retraces to fill. Strategy enters on retracement into the gap with the gap's direction as bias.

## Key params
(Not yet tuned — using engine defaults)

## Result
Not yet validated against the Phase 1-8 workflow. This was the fifth canonical strategy in the engine's original demo lineup; moved here because it's a discretionary pattern-based strategy that doesn't have the same academic backing as the momentum/mean-reversion strategies that stayed in the engine.

## TODO
- Run `experiments/imbalance/imbalance_demo.py` on the 24-instrument universe
- Phase 3: statistical battery
- Phase 4: regime stability
- Phase 5: parameter sensitivity (gap-size threshold, retracement tolerance, hold duration)
- Phase 6: holdout

## Files
- Strategy: `research/imbalance.py`
- Demo: `experiments/imbalance/imbalance_demo.py`

## References
- ICT / SMC trading literature (not peer-reviewed; treat with skepticism)
