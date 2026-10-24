# RASD — external Cloudflare Free clock: deployment and acceptance

**Scope:** External UTC clock only. RASD content, original publisher screenshots, Gmail, private acceptance ledger and daily 22:00 Cairo rollup **remain entirely on protected GitHub Actions**. No Railway. Do not edit or reveal SMTP secrets.

## Production architecture

1. Cloudflare Workers Free `scheduled()`: cron `7,37 * * * *` UTC, two times per hour (48/month-day).
2. Worker uses one encrypted Cloudflare secret: `GH_ACTIONS_TOKEN`. The sole network action is POST `/repos/Hatem1984/RASD-Cloud-Monitor/actions/workflows/rasd-cloudflare-dispatch.yml/dispatches` with `ref=main` and a UTC scheduled slot.
3. GitHub requires the exact repo, workflow, `Hatem1984` actor, named origin and fresh UTC scheduled slot before allowing *either* private-ledger or Gmail access. A GitHub job launched >20 minutes after the scheduled timestamp stays HOLD.
4. Worker creates no reports and sends no Gmail. Native GitHub schedules and Cloudflare-dispatched runs share **one repository-wide concurrency group** and existing private compare-and-swap acceptance ledger. A suspected SMTP success is never blindly retried.
5. A separate GitHub job handles the Cairo 22:00 daily recovery in the same safe worker, respecting DST and the one-daily-report ledger key.

## Provisioning (never put tokens in repository, commits, GitHub issue, chat or terminal history)

- Cloudflare account must be signed into Wrangler on the authorized owner's machine. Command from an interactive terminal: `npx wrangler@4 login`. Browser OAuth approval is performed **only by the owner**; do not use a shared account.
- In GitHub, issue a **fine-grained personal access token** for the `Hatem1984` owner, repository **RASD-Cloud-Monitor only**, with repository **Actions: Read and write** permission and a suitable expiry. No Contents write, Administration, Secrets or unrelated repository permissions are required for workflow-dispatch. GitHub's REST dispatch requires Actions:write.
- From the folder `cloudflare-rasd-clock`, add it privately using `npx wrangler@4 secret put GH_ACTIONS_TOKEN`; enter the token in the secure prompt (not command-line args). Confirm it is not printed in logs.
- Deploy from that folder with `npx wrangler@4 deploy` after the secret exists, or deploy and then provision the secret, checking **Cron Triggers** is active in Cloudflare Dashboard. The Worker has `workers_dev=false`, and its `fetch()` endpoint returns 404; **no public HTTP trigger is available**.
- Review Cloudflare scheduled invocation `RASD_CLOUDFLARE_DISPATCH_ACCEPTED`; review the resulting **GitHub `workflow_dispatch` job**, then the private delivery state and recipient Inbox. A 204 API response proves only GitHub accepted the dispatch, not news delivery.
- The native GitHub cron stays enabled as a recovery layer. To emergency-stop *both* production paths, set repository Actions variable `RASD_AUTOMATION_PAUSED=true`. To revoke external triggering, delete the Cloudflare `GH_ACTIONS_TOKEN` secret or revoke the GitHub token.

## Free-tier & operational boundaries

This design requires 48 cron invocations per day, and 1 Cloudflare cron trigger, within published Workers Free limits (subject to other account usage). GitHub Actions runtime, publisher availability, native RSS freshness and token expiry are independent operational limits. Cloudflare Cron Triggers do not imply hard wall-clock SLA or guaranteed Google Inbox delivery.

**Release stages:**
- `CODE_READY`: protected GitHub dispatch job and Cloudflare Worker source merged; Python CI green.
- `CLOUDFLARE_DEPLOYED`: authenticated Cloudflare owner deployed Worker, provisioned GH secret, visible cron trigger.
- `PRODUCTION_ACCEPTED`: at least two distinct scheduled events show GitHub runs and no duplicate Word deliveries, and 22:00 Cairo daily report validated independently.

Do not claim `CLOUDFLARE_DEPLOYED` or `PRODUCTION_ACCEPTED` merely because GitHub CI passed.
