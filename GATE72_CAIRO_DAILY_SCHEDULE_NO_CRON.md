# Gate72 — Cairo-calendar daily schedule preflight (NO CRON)

20 October 2026. `gate72_cairo_schedule_dryrun.py` is pure scheduling arithmetic; it does NOT create a GitHub/OS scheduler, send Gmail, touch R2, read private credentials or approve production. Existing user-facing ChatGPT task monitoring of RASD is separate from RASD's future automated report pipeline and must not be confused with real delivery.

## Correct future schedule
- Proposed reporting time **08:00 Africa/Cairo**, with Python IANA timezone rather than hardcoded UTC offset (Egypt switches seasonal DST).
- Target is exactly **the previous COMPLETED Cairo calendar date**. This never interprets an incomplete today as accepted. Same previous-date report gets the SAME Gate70 24-hex idempotency identity in the entire local day.
- Before 08:00 => `WAIT_CAIRO_LOCAL_08_00_NOT_DUE`; 08:00 to 08:59 => `DRYRUN_READY_WINDOW_ONLY`; 09:00 onward => `MISSED_WINDOW_REQUIRE_OPERATOR_REVIEW_NO_AUTO_CATCHUP`. No job is launched in any case. There is NO uncontrolled replay/retro-send after an outage.
- A future owner-approved operational schedule must also check actual Stage2 full-source and original screenshot evidence, genuine Gate61/62 local human acceptance, healthy current source, configured private R2 restore proof, Gmail protected send and private receipt ledger, and explicit launch authorization before enabling any automated delivery. These gates are NOT currently met.

## Tests and security
Offline unit tests cover Cairo GMT+2/+3 winter/summer DST, prior-full-day semantics, 07:59/08:00/08:59/09:00 boundaries, stable no-send idempotency day ID, next-day turnover, absent timezone and no credentials/network/cron. Neither GitHub Actions `schedule:` nor third-party scheduler was enabled.

The production scheduler is **NOT DEPLOYED**, and a successful planner test is **not** proof of real repeated unattended delivery. Stage1 human review #42, upstream source #53, protected Gmail #36 and real R2 #35 remain separately open.
