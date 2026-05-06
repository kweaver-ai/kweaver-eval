# Bug Report: `kweaver` CLI persists un-normalized platform identifier, causing scheme-less `baseUrl` on subsequent calls

- **CLI version**: `kweaver` 0.6.5
- **Observed**: 2026-04-20 during a `kweaver-eval` `make test-at` run (13:21–13:34 local)
- **Severity**: high — reliably breaks any command whose code path resolves to the bad platform entry; failures look like CLI code bugs (`Failed to parse URL from 192.168.40.62/api/...`) but are actually local state corruption.

## Summary

The CLI stored a platform directory keyed by a **raw, scheme-less host string** (`192.168.40.62`), with its `token.json::baseUrl` set to the same scheme-less value. `state.json::activeUsers` then ended up with three sibling entries for the same host — `https://192.168.40.62`, `http://192.168.40.62`, and bare `192.168.40.62` — all pointing at the same `default` user. Platform resolution at call time non-deterministically picks the bare entry on some routes, which feeds `""192.168.40.62""` into `new URL(...)` and throws `TypeError: Invalid URL` before any network I/O.

This is **not** the URL-construction code's fault. `packages/typescript/src/api/agent-list.ts` builds every v3 route with the same template:

```ts
const base = baseUrl.replace(/\/+$/, "");
const url  = `${base}/api/agent-factory/v3/...`;
```

`normalizeBaseUrl()` in `auth/oauth.ts:393` likewise only strips trailing slashes. Neither strips a scheme. The defect is that `baseUrl` was **already** scheme-less when it came out of the stored `token.json`.

## Reproduction / Evidence

On the reporter's machine:

```
~/.kweaver/platforms/
  aHR0cDovLzE5Mi4xNjguNDAuNjI/               # base64("http://192.168.40.62")  — good
  MTkyLjE2OC40MC42Mg/                         # base64("192.168.40.62")        — bad
  aHR0cHM6Ly8xOTIuMTY4LjQwLjYy/               # base64("https://192.168.40.62") — also present
  ... (other platforms)
```

Bad entry contents:

```
$ cat ~/.kweaver/platforms/MTkyLjE2OC40MC42Mg/users/default/token.json
{
  "baseUrl": "192.168.40.62",
  "accessToken": "__NO_AUTH__",
  "tokenType": "none",
  "scope": "",
  "obtainedAt": "2026-04-20T05:26:02.088Z"
}
```

`state.json` registers all three keys for the same host:

```
"activeUsers": {
  "https://192.168.40.62": "default",
  "http://192.168.40.62":  "default",
  "192.168.40.62":         "default",
  ...
}
```

Timeline during the failing test run (local times, same host only):

| Time | File written |
|---|---|
| 13:26:02 | `platforms/MTkyLjE2OC40MC42Mg/users/default/token.json` (no-scheme) |
| 13:26:14 | `platforms/aHR0cDovLzE5Mi4xNjguNDAuNjI/users/default/token.json` (`http://`) |

Twelve seconds apart — strong hint the bad entry was produced by the same command that later produced the good one, i.e. a two-step flow that bookmarks the raw user input before normalizing.

## Symptoms observed downstream

Within a single `kweaver-eval` pytest session:

| Command | Result | Stderr (abridged) |
|---|---|---|
| `agent personal-list` | OK | — |
| `agent template-list` | OK | — |
| `agent chat <id> --no-stream` | OK (mostly) | — |
| `agent list` | exit 1, ~131 ms | `Failed to parse URL from 192.168.40.62/api/agent-factory/v3/published/agent` |
| `agent create ...` | exit 1, ~131 ms | `Failed to parse URL from 192.168.40.62/api/agent-factory/v3/agent` |
| `agent get-by-key ...` | exit 1, ~126 ms | `Failed to parse URL from 192.168.40.62/api/agent-factory/v3/agent/by-key/...` |
| `agent chat <id> --stream` | exit 1, ~130 ms | `URL: 192.168.40.62/api/.../version/v0?is_visit=true  Cause: Invalid URL` |

The ~130 ms wall-clock (well under any network RTT) confirms the failure is pre-flight — `new URL()` throwing in `fetch`, not a network error.

## Why this isn't a "subset of routes drops scheme" bug

It looks like a per-route bug from the outside because within one session some routes succeed and others fail. The real explanation is that different call sites resolve the "current platform" via different paths (e.g. some go through `state.json::currentPlatform`, some look up `activeUsers` by host, some via `KWEAVER_USER` or cached process state). When the `activeUsers` map contains three keys that collide on host-without-scheme, the resolver can land on the bad entry for some routes and the good one for others. The code that *constructs* the URL is uniform across routes.

## Where to look

Two defects to investigate; either alone is sufficient for this bug, but both matter:

1. **Platform registration doesn't normalize input**
   - Any code path that writes to `~/.kweaver/platforms/<key>/` or to `state.json::activeUsers` must first normalize the platform identifier to `scheme://host[:port]`, with scheme defaulted (to `http://` or whatever the probe resolved) when the user/env provided a bare host.
   - Grep for writers: anywhere you construct the platform directory name (likely a `base64url(identifier)` helper) or add to `activeUsers`. Ensure every writer goes through a single `normalizePlatformId(input)` helper, and that helper *rejects* or *upgrades* bare-host inputs.
   - Check especially auto-register / fallback-probe logic: the reporter's repo has **no** test code that runs `auth login` / `platform add`, yet the bad entry was written during a normal-command test run — so some non-login code path is doing the write.

2. **Platform resolution tolerates aliases**
   - Even once registration is fixed, an already-corrupt `state.json` will keep misbehaving. The resolver should treat `activeUsers` keys as canonical URLs (scheme required) and either migrate or ignore bare-host keys on load.
   - A one-shot migration in CLI startup (detect bare-host keys, merge them into the schemed sibling, rewrite `state.json`) would repair affected users without manual cleanup.

## Suggested reproduction inside the CLI repo

```bash
rm -rf /tmp/kw && mkdir -p /tmp/kw
HOME=/tmp/kw kweaver auth login 192.168.40.62 -u x -p y        # or whatever login flow applies
ls /tmp/kw/.kweaver/platforms/                                  # expect ONE dir, scheme-qualified
cat /tmp/kw/.kweaver/platforms/*/users/*/token.json | jq .baseUrl
# expect "http://192.168.40.62", NOT "192.168.40.62"
```

Additionally, enumerate every code path that can write under `platforms/` or mutate `activeUsers`, and verify each goes through `normalizePlatformId`.

## Workaround (for users hitting the symptom today)

```bash
# Inspect
ls ~/.kweaver/platforms/
python3 -c 'import base64,sys; [print(d, "->", base64.b64decode(d + "="*(-len(d)%4)).decode(errors="replace")) for d in sys.argv[1:]]' ~/.kweaver/platforms/*/.../  # decode dir names

# Remove bad entry (back up ~/.kweaver first)
rm -rf ~/.kweaver/platforms/<bare-host-base64-dir>
# Edit ~/.kweaver/state.json and delete activeUsers keys that lack a scheme.
```

## Not in scope for this report

- Token / auth logic itself: the stored `accessToken` is `__NO_AUTH__`, and the bug reproduces identically for authenticated platforms — the failing field is `baseUrl`, not anything auth-related.
