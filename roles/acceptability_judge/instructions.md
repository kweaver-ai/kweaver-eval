# Instructions

Evaluate the test case execution results and produce a JSON verdict.

## Input

You receive:
- Test case name and description
- CLI execution steps with stdout/stderr/exit_code
- Deterministic scoring results (if available)

## Output Format

Respond with ONLY a JSON object (no markdown, no explanation outside JSON):

```json
{
  "verdict": "pass|fail|warn",
  "findings": [
    {
      "severity": "critical|high|medium|low",
      "message": "Description of the finding",
      "location": "Which step or assertion"
    }
  ],
  "reasoning": "Brief overall assessment"
}
```

## Severity Guide

- **critical**: System broken — command crashes, data loss, auth failure blocking all operations
- **high**: Major feature broken — expected data missing, wrong results, >10s latency
- **medium**: Minor issue — warning messages, suboptimal output format, slow but functional
- **low**: Cosmetic — extra whitespace, verbose output, minor inconsistencies

## Verdict Rules

- Any critical finding → verdict: "fail"
- Any high finding → verdict: "fail"
- Only medium/low → verdict: "warn"
- No findings → verdict: "pass"
