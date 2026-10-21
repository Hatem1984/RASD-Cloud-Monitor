# RASD — cloud-only 30-minute newsroom alerts + Cairo end-of-day digest

**Status: proposed, OFF until owner activation.** This implementation uses GitHub-hosted workers only. The previously manually-triggered Gate11/Gate13 workflows are preserved; this is a separately authorized sender/recipient route. **No owner Windows or browser session is needed during scheduled operation.**

## Execution

- GitHub Actions `0,30 * * * *` discovers matching news in the reviewed external publisher-owned RSS feeds every half hour. GitHub can delay or occasionally drop scheduled jobs: not an exact clock/uptime guarantee.
- New news only: private GitHub CAS ledger keys are original publisher canonical article IDs. On first production activation, the previous 24h RSS matching items may be considered new. An operator must perform a no-send baseline review before enabling.
- No matches: no fabricated news, no empty illustrated email. RSS unavailable, >15 eligible items, failed publisher screenshots, swapped Word JPEG or SMTP uncertainty: HOLD, not an invented success or automatic blind retry.
- Every selected item: direct original newsroom URL, publisher/date/title, genuine Chromium publisher screenshot, SHA-256-verified attachment Word. No Ministry-government-owned site is counted as newsroom coverage.
- Private ledger reserves all article keys atomically **before** SMTP and stores only private per-article metadata. Every accepted item is marked `smtp_accepted` only after Gmail SMTP accepts it; this status **does not prove inbox receipt**. A partial receipt-update failure remains HOLD rather than re-sending.
- `0 19,20 * * *` provides two UTC candidates so precisely the Cairo-22:00 occurrence is eligible across summer/winter DST. The competing 22:00 half-hour slot is intentionally SKIPPED (the next polling occurs at 22:30) to avoid a same-minute race. GitHub may delay actual execution. The report includes SMTP-accepted interval alerts in the **rolling previous 22:00-to-current 22:00 Cairo delivery window**: this prevents alerts sent after 22:00 from vanishing at midnight. The worker re-opens original publisher articles, re-captures page screenshots, and sends one consolidated Word (up to 60 items). Daily re-capture failure → HOLD rather than incomplete aggregation. If no accepted stories exist, no fake digest is sent.
- Serial GitHub Actions concurrency group prevents overlapping interval/rollup jobs. Email sending is at most once per reserved news key, with manual reconciliation required for uncertain SMTP outcomes.

## REQUIRED owner-only activation: private account setup on GitHub

1. Establish a **dedicated Gmail sender**, separate from the recipient, for RASD; never use a personal Gmail inbox as a substitute for system mail transport. App-specific password (if supported) or a future OAuth review. No secrets in chat/commits.
2. Ensure private `Hatem1984/RASD-Pilot` branch `rasd-private-delivery-state` has the existing `delivery-state.json` version 2 with approved recipient SHA-256 equal to the intended recipient. Set a fine-grained contents RW token restricted to that private repo only. The repo public code MUST NOT include emails, tokens, news snapshots, Word files or screenshots.
3. Create environment `rasd-production` at `Hatem1984/RASD-Cloud-Monitor/settings/environments`. Restrict deployment to `main`. Scheduled jobs cannot satisfy a required human reviewer on **each half-hour run**, so require protected branch reviews before enabling; scope credentials carefully and never give them to untrusted PRs. Store environment secrets:
   - `RASD_GMAIL_SENDER` — new dedicated Gmail sender.
   - `RASD_REPORT_TO` — recipient; MUST differ from sender, and hash must match private ledger approved recipient.
   - `RASD_GMAIL_APP_PASSWORD` — sender's limited app password.
   - `RASD_PRIVATE_LEDGER_TOKEN` — token restricted to `RASD-Pilot` only.
4. First test `Actions > RASD — 30-minute newsroom monitoring + Cairo daily rollup > Run workflow` on `main`. This is **no-send clock/test preview**. Then separately test protected production credentials in a controlled manual preflight and an explicitly reviewed real send, confirming received DOCX JPEGs and private delivery receipt. No private send occurs just by running workflow_dispatch.
5. **Only after acceptance:** create repository Actions variable `RASD_AUTOMATION_ENABLED = true`. **Unset/missing means all schedule jobs are skipped**; setting the flag is the explicit irreversible opt-in to repeatedly sending real email.
6. Check Gmail's sending quota, GitHub scheduled-run capacity, private ledger growth and source rate limits; update approved publishers only via review. Production `sources.json` remains the preserved two RSS feeds. Include Shorouk only after independently approving its native RSS stability.

## Known limitations / honest operational risks

- GitHub scheduled workflows are best-effort, not guaranteed to fire exactly each half hour. A dedicated managed queue/worker is needed for strict delivery SLA.
- Native RSS feeds may show only recent news and are not an exhaustive internet/media crawler. An article not in an approved RSS feed won't be discovered until adding a vetted source or a compliant search adapter.
- Source title/date semantic dedup is **not** yet a reliable independent-event classifier; current dedup is canonical URL/article identity. Multiple outlets covering the same event may be included as separate media hits.
- An uncertain SMTP send or private ledger state must be reconciled by an authorized operator; no automatic replay. Daily screenshots are re-fetched, and any removed/unavailable source article can block exact daily rollup.
- The private ledger v2 max 20,000 entries will require retention policy and archival before reaching capacity.
- Do NOT claim automation is LIVE until actual hosted schedule run + real separate-address Gmail email + daily reconciliation verified.