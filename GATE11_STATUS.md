# RASD — Gate 11 secure autonomous-mail bridge (implementation in progress)

## Proven starting point
Gate 10 was closed: 29/29 hosted tests in each of 3 manual workflows; public-state run_count=3. This new implementation does not rewrite or migrate that public observation state.

## Scope and trust boundaries
- Public repository: public RSS discovery, original publisher screenshot, and source code only.
- Private repository: existing RASD-Pilot, private branch \`rasd-private-delivery-state\`, private \`delivery-state.json\`. Only article hashes, reservation times, Gmail SMTP acceptance message IDs and acceptance times can be persisted there. No full screenshot or news text.
- Gmail account: sender and only recipient must be identical and protected in GitHub Actions **environment secrets**. The ChatGPT Gmail connector is **not** available to GitHub runner.
- Workflow \`gate11-manual.yml\` has only \`workflow_dispatch\`, default \`dry_run\`, with read-only GitHub token. No \`schedule\`/cron, no automatic delivery from push, no public artifact upload.
- Mode \`send\` requires a manually dispatched run on \`main\`, a separately configured protected environment, all five secrets, and the exact approval string. No secret has been provisioned by this code change.
- Environment \`rasd-gmail-manual-approval\`: if enabling later, configure a **required reviewer** and restrict deployment branches to main; do not store credentials in repository variables, code, logs, PR comments, local Windows PC, or chat.
- Restrict access to the PUBLIC repository (write collaborators), since editors can modify workflows. Before placing secrets, review merged code and secure default branch against unreviewed changes.

## Future protected GitHub environment secret names
- \`RASD_GMAIL_USER\`: the previously approved Gmail account, also the sender.
- \`RASD_APPROVED_RECIPIENT\`: the same previously approved Gmail account; the code refuses a mismatch.
- \`RASD_GMAIL_APP_PASSWORD\`: optional Google account app password *only if* supported by the account and expressly approved. Google 2-Step Verification and account eligibility apply. Never use the normal Gmail account password.
- \`RASD_PRIVATE_LEDGER_TOKEN\`: fine-grained GitHub token with contents read/write on **only** the existing private RASD-Pilot repository; not a classic broad PAT.
- \`RASD_GATE11_SEND_APPROVED\`: exact phrase \`YES_I_APPROVE_GMAIL_DELIVERY\`, created only after explicit go-live consent.

**Do not create or disclose these secrets until the account security, test scope and $0 eligibility have been verified.** Secret handling has not been executed by the GitHub connector.

## Email lifecycle
1. Read reviewed native RSS. Reject missing publisher date, old news, historical screenshot fixture, cross-domain original URL, unknown source, malformed fingerprints, and headlines without a trusted publishing provenance.
2. Capture the *same* original news article. Reject redirecting to a different canonical URL, visually rejected screenshot, and screenshot browser title not matching original publisher headline.
3. On protected send only, check private ledger. If already SMTP accepted, skip. If reserved/hold, **do not retry automatically**.
4. Reserve the article hash in private GitHub state with SHA compare-and-swap **before** SMTP. If private write fails, send nothing.
5. Submit through Gmail SMTP over TLS to sender==recipient only with original headline/URL and verified JPEG. No second receiver.
6. Mark \`smtp_accepted\` in the private ledger after SMTP acceptance. This status is **NOT** a proof of arrival in Inbox.
7. If SMTP or state write is uncertain, leave \`reserved\`; human must reconcile against Gmail Sent/Inbox before changing state. This biases toward missing an alert rather than duplicates.

**Important:** No distributed system can guarantee exactly-once user-visible email delivery solely with SMTP plus GitHub commits. The implementation prevents automatic repeated sends after a recorded reservation but might require manual reconciliation following a crash. Private state has bounded capacity and fails closed rather than expiring sent history and accidentally duplicating old alerts.

## Test and release criteria
- [x] Private branch and empty ledger provisioned on existing private repo.
- [x] Offline SMTP/ledger/test-fixture safety suite on public hosted runner.
- [x] Hosted live RSS dry-run: run 38333307545 PASS, eligible=0, captured=0, SMTP=0, fixtures=0, schedule OFF. This verifies safe zero-match behavior, not actual delivery.
- [ ] Required reviewer/environment protection established; 5 GitHub secrets safely provisioned if SMTP app password route is eligible.
- [ ] One expressly approved real Gmail submission of a genuinely NEW eligible original-source story; SMTP-accepted private receipt read-back.
- [ ] Gmail Sent and Inbox read-back, including attachment verification.
- [ ] Second manual run proves no auto-resend; an uncertain state stays on hold.
- [ ] Gate 11 CLOSE after all true end-to-end evidence. Current status: **PARTIAL — NO REAL MAIL FROM THE CLOUD WORKER**.

## Hosted evidence
- [Gate 11 branch CI: 44 offline tests PASS + genuine current-feed dry-run PASS](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38333307545)
- The feed yielded no eligible current planning article. No screenshot and no mail resulted; screenshot code is covered by Gate 10 and fixture/unit regressions, not by a Gate 11 live-match proof.

## Cost notes
Standard GitHub-hosted Ubuntu runners in a public repository are currently free by official GitHub pricing. The new Gate 11 pipeline uploads no artifacts. Private RASD-Pilot Actions are not invoked. Artifact/storage quotas, service terms and account eligibility must still be checked before automatic scheduling. No cost authorization or billing change is requested.

## Gate 11 hardening verification (13 October 2026)

- The separate private ledger has been safely upgraded from empty schema v1 to empty schema v2. It holds the fingerprint of the single approved recipient and never stores email credentials.
- The cloud delivery code now rejects any sender inconsistent with that independently stored private fingerprint, even if both Actions address settings accidentally match an unapproved mailbox.
- GitHub private-ledger API redirects are rejected before bearer credentials can be sent to another destination.
- Hosted CI: 50 out of 50 offline tests passed, including mocked real GitHub Contents API state commits, conflict rejection before SMTP, and duplicate suppression.
- Hosted live-source dry-run also passed, with zero eligible articles and zero Gmail sends. Evidence: https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/38334975735
- Real Gmail credentials remain unconfigured; no real SMTP send, inbox verification, or automatic schedule. Gate 11 still OPEN.
