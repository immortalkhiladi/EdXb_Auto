# Load test and fixes report (2026-10-17)

## Test environment
- Production settings (`config.settings.production`), started with `backend/startup.sh` (gunicorn: 2 gthread workers × 4 threads), with TLS in front.
- PostgreSQL 16.
- The server ran inside a cgroup limited to **0.5 CPU / 512 MB RAM**, which matches the Render `starter` plan.
- Load was generated with Locust using 100 seeded USER accounts.
- Each simulated user did: SPA load, CSRF, login, `me`, document list and search, tool list, tool frame, upload (`process`), view, download, plus periodic logout and re-login.

## Results

| Run | Users | Requests | Failures | OOM kills | Peak memory |
| --- | --- | --- | --- | --- | --- |
| **Before fixes** | 70 (1–3 s think time) | 3,670 | **~2,250 (61 %)**: 205 logins rejected with 429, worker killed for running out of memory, connection resets, then a cascade of 401s | **1** | 512 MB (at the limit) |
| After fixes, steady state | 70 (1–3 s think time) | 5,121 | **0** | 0 | 238 MB |
| After fixes, first sign-in after deploy (old password hashes) | 70 | 3,821 | **0** | 0 | 389 MB |
| After fixes, first sign-in after deploy (final build, instance-wide hash lock) | 70 (3–10 s think time) | 1,042 | **0** | 0 | 348 MB |

- **Steady state, after fixes:** median 11 ms, p95 670 ms, about 43 requests/s on 0.5 CPU.
- **First sign-in after deploy:** response times are high while each user's old hash is verified once (p95 about 19 s). This happens only on each user's first login after the deploy; the hash is then upgraded automatically.
- **Backend tests:** 140 passed and 2 skipped on SQLite; 141 passed and 1 skipped on PostgreSQL. This includes 8 new regression tests in `tests/test_load_hardening.py`.
- **Frontend:** 16 tests passed, the production build succeeds, and `npm audit` reports 0 vulnerabilities.

**Not completed (testing was stopped on request):**
- The 150-user stress test and a final steady-state rerun of the final build.
- A test on a real Render deployment.

## Bugs found and fixed

### Critical
1. **Logins failed for an office sharing one IP.** The only login limit was 20 attempts per IP per 10 minutes, so the 21st colleague behind the same NAT got 429.
   - **Fix:** the limit is now per IP + account (`LOGIN_RATE_LIMIT`), plus a separate per-IP ceiling (`LOGIN_IP_RATE_LIMIT`, default 300).
   - Brute-force and password-spraying protection is kept and tested. The same change was made for MFA.
2. **Workers ran out of memory and were killed.** Django's default Argon2 settings use 100 MB of RAM and about 0.5 s of CPU per hash (at 0.5 CPU). With 8 threads, a burst of logins exceeded 512 MB.
   - **Fix:** a new `portal/hashers.py` uses the OWASP Argon2id parameters (m = 19 MiB, t = 2, p = 1). These are configurable through `ARGON2_*` environment variables.
   - At most one hash runs at a time across all workers on the instance (`PASSWORD_HASH_CONCURRENCY`, enforced with a file lock).
   - Old hashes still verify and are re-hashed automatically at each user's next login.

### High / medium
3. The failed-login counter could lose increments when attempts ran concurrently. It is now an atomic `F()` update.
4. Every successful login wrote `failed_attempts` to the database. It is now written only when the value is not already 0.
5. ZIP and text previews read the whole file into memory with no limit on how many could run at once.
   - ZIP previews now read straight from the file.
   - At most `PREVIEW_CONCURRENCY` (default 2) previews run at once per worker.
6. **Client IP could be forged.** The left-most `X-Forwarded-For` entry is client-controlled, which affects rate limiting and the IPs in audit logs.
   - **Fix:** new `PROXY_HOPS` setting. The default `0` keeps the old behaviour.
   - **Action for you:** set it to the number of trusted proxies in front of the app, after checking how Render builds this header.
7. gunicorn changes:
   - `--max-requests` with jitter, so workers are recycled periodically.
   - `--graceful-timeout` and `--keep-alive`.
   - The worker heartbeat file goes to `/dev/shm` when it exists.
   - `MALLOC_ARENA_MAX=2` to keep worker memory from creeping up.
8. Frontend:
   - The Dashboard re-sent 3–4 API calls every time the user switched back to the tab.
   - The documents table could show results from an older request that arrived late.
   - The table showed an empty page after deleting the last row of the last page.
   - An expired session was not detected when the user returned to the tab or opened a tool page (the tool showed raw JSON).
   - With an expired session, a large upload was sent twice before failing.
   - The whole app went blank when browser storage was blocked.
   - Closing a modal could re-enable page scrolling while another modal was still open.
   - File sizes of 1 TB or more were shown as "undefined".

## Found but NOT changed (needs your decision)
- **Password policy allows only 4–6 characters.** This is a significant security weakness. It is a documented product rule with tests, so it was left unchanged. Recommendation: a minimum of 12 characters.
- `PASSWORD_RESET_REVEAL_ACCOUNT` defaults to `true`, which lets anyone check which email addresses have accounts. Recommendation: `false` in production.
- **The "Request a Filing Quote" form on the login page sends nothing.** It always shows success, so whatever the user enters is lost.
- Rate limits are kept in memory per worker, so with 2 workers the effective limits are doubled. The per-account lockout is stored in the database and remains the main protection.
- The README says `seed_users` creates random passwords. It actually uses fixed default passwords (Admin@123 / User@123).
- The uploaded package included `backend/data/.dev_secret_key`. It is removed from this zip; generate a new one locally.
- The login background image is 1 MB. Consider compressing it.
- On a 0.5 CPU instance the first morning after deploy will be slow, as noted above. A larger plan (1 CPU) would roughly halve that delay.
