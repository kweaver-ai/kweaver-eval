# Instructions

Generate an aggregate health report from a complete evaluation run.

## Input

You receive:
- All case results (deterministic + agent judge) from the current run
- Feedback tracker data (cross-run persistent issues)
- Prior run summary (if available)

## Output Format

Respond with ONLY a JSON object:

```json
{
  "overall_status": "healthy|degraded|broken",
  "summary": "One paragraph overall assessment",
  "sections": [
    {
      "title": "Section title",
      "content": "Section content (markdown)"
    }
  ],
  "top_issues": [
    {
      "severity": "critical|high|medium|low",
      "message": "Issue description",
      "affected_tests": ["test_name1", "test_name2"],
      "suggested_action": "What to do about it"
    }
  ]
}
```

## Required Sections

1. **Overview** — pass/fail ratio, overall health verdict
2. **Critical Issues** — anything blocking (if any)
3. **Persistent Issues** — items seen 3+ times across runs
4. **Trends** — comparison with prior run (if available)
5. **Recommendations** — prioritized next actions
