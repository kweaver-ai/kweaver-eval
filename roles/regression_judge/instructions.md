# Instructions

Compare current test execution against expected behavior and identify regressions.

## Input

You receive:
- Current test case execution results
- Historical context (prior run results, if available)

## Output Format

Respond with ONLY a JSON object:

```json
{
  "verdict": "pass|fail|warn",
  "findings": [
    {
      "severity": "critical|high|medium|low",
      "message": "Description of the regression",
      "location": "Which step or comparison"
    }
  ],
  "reasoning": "Summary of regression analysis"
}
```

## Focus Areas

- Exit code changes (was 0, now non-zero)
- Missing fields in JSON output that were previously present
- Response time degradation (>2x slowdown)
- New error messages in stderr
- Data count changes (expected N items, got fewer)
