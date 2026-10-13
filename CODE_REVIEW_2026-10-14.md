# RASD | Engineering audit and safe housekeeping — 14 October 2026

Scope: the public RASD Cloud Monitor source, seven GitHub Actions workflows, offline tests, and the existing separation of public reports from the private delivery ledger. No user Windows files or historical Git branches were removed.

## Fixed and verified

| Finding | Change | Risk handled |
| --- | --- | --- |
| Two first-feed articles could crowd out a newer second-publisher alert | Request the bounded validated RSS pool and sort eligible original-publisher candidates by UTC publication timestamp | Avoid missing the newest eligible story simply because it came from the second source |
| Naive timestamps were accepted at RSS entry points | Reject timestamps lacking timezone before network calls | Avoid silent time-window errors and misleading source-health failures |
| CI branch list contained thirteen increasingly stale names | Use `main` plus a single `gate*` pattern | Future QA branches run the same checks without copying old branch names |
| Repeated CI commits consumed concurrent runner time | Cancel only superseded read-only CI runs for the same branch | No cancellation or scheduling changes to protected manual mail workflows |
| Local evidence, `.env` files, private keys, caches and generated documents were not ignored | Add dedicated `.gitignore` rules | Lower accidental local-data commit risk without deleting or changing any tracked historical data |
| Screenshot rejection was counted without a reason | Add aggregated allowlisted failure codes (all unknown inputs collapse to `other`) | Operational diagnosis without printing URL, page text, exception contents or credentials |
| Regression blind spots | Add dedicated housekeeping, screenshot-privacy, naive-clock and cross-publisher ordering tests | Repeatable hosted CI validation |

## Verified hosted checks

The [Gate 16 final logic run](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38476555595) passed **114/114 tests** and both GitHub jobs. Live public RSS validation reported **two healthy sources**, **30 publisher links**, and **one matching headline**. Both source-backed Arabic document files were created and structurally verified; the downloadable CI artifact exists.

The publisher browser capture **did not pass** for the new matching story. Diagnostic code: `publisher_http_failure` (one occurrence). This indicates that the source page did not return an acceptable HTTP response to the isolated capture browser. It is NOT proof of a successful screenshot, and the worker correctly refused to send that image. Resolve this as a separate publisher-access and browser QA issue; never bypass a website challenge or use a historical reference as if it were a live article.

## Unchanged security boundaries

- Production Gmail SMTP, real inbox acceptance, and any scheduled mail remain OFF / unverified.
- The private delivery ledger remains separate. No new private state entries were created during this audit.
- Manual protected email workflows and reviewer approvals remain unchanged.
- No paid connector, external browser service, local file cleanup or history destruction was used.
- Successful CI is not equivalent to a live authorized email or production-news screenshot acceptance.

## Outstanding acceptance

1. Diagnose original publisher HTTP behavior without bypassing access controls; retain fail-closed capture until a real current-page screenshot passes.
2. Finish account-level protected credential provisioning and verify a manual authentication-only preflight.
3. Conduct separately authorized real mail tests and private receipt/inbox readback.
4. Authorize and stage any schedule only after the above gates, with explicit costs and operational failure alerting.
