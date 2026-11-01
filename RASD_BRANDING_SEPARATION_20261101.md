# RASD display brand separation — REVIEW ONLY

RASD is the Ministry of Planning reporting system, independent from MA'AL Business AI.

This patch returns generated RASD email subjects, report titles and report text
from «مآل» to «رصد». It does not modify recipient addresses, email Message-IDs,
the X-RASD-Delivery-ID header, CAS/idempotency keys, journal or original evidence.

Historical fixture documents and old archived emails are not retroactively rewritten.
Do not merge to production until owner explicitly accepts the subject/title change
and confirms that recipients or email filters do not depend on the former subjects.

QA: offline tests including document rendering; do not send email.
