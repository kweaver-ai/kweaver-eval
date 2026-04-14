# Check Environment

Verify that the kweaver-eval runtime environment is ready for acceptance testing.

## Checks

Run each check in order. If any check fails, stop and write the gate artifact
with `ready: false` and the failure details.

### 1. CLI authentication

```bash
kweaver auth status
```

**Pass condition:** exit code 0, stdout contains "Token status:".

### 2. Backend reachability

```bash
kweaver vega health
```

**Pass condition:** exit code 0.

### 3. Test collection

```bash
cd ~/dev/github/kweaver-eval && python3 -m pytest tests/ --collect-only -q
```

**Pass condition:** exit code 0, output shows collected test count > 0.

### 4. Required environment variables

Check that these are set and non-empty:
- `KWEAVER_BASE_URL`

Read the `.env` file at `~/dev/github/kweaver-eval/.env` and `~/.env.secrets`
to see if values are present (either in the environment or in those files).

## Gate artifact

Write `{stage}/{role}/result.json`:

```json
{
  "ready": true,
  "checks": {
    "auth": "pass",
    "backend": "pass",
    "test_collection": "pass",
    "env_vars": "pass"
  }
}
```

If any check fails, set `ready` to `false` and change that check's value to a
string describing the failure (e.g., `"auth": "FAIL: exit code 1 — not authenticated"`).
