// External RASD clock only: no Gmail credentials, private ledger or public trigger.
const INTERVAL_CRON = "7,37 * * * *";
const DAILY_CRON = "0 19,20 * * *";
const OWNER = "Hatem1984";
const REPO = "RASD-Cloud-Monitor";
const WORKFLOW = "rasd-cloudflare-dispatch.yml";
const INTERVAL_ORIGIN = "cloudflare-rasd-cron-v1";
const DAILY_ORIGIN = "cloudflare-rasd-daily-v1";
const WORKFLOW_URL = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}`;
const GH_HEADERS = {
  Accept: "application/vnd.github+json",
  "X-GitHub-Api-Version": "2022-11-28",
  "User-Agent": "RASD-Cloudflare-Cron/1.1",
};

function githubToken(env) {
  // Cloudflare may show the secret NAME in settings even when the latest
  // runtime cannot access a valid token. Report ONLY a status code, never a
  // value, prefix, length or object dump.
  const raw = env.GH_ACTIONS_TOKEN;
  if (raw === undefined || raw === null) {
    throw new Error("github_secret_binding_unavailable");
  }
  if (typeof raw !== "string") {
    throw new Error("github_secret_binding_nontext");
  }
  const token = raw.trim();
  if (token.length < 40) {
    throw new Error("github_secret_binding_too_short");
  }
  if (!token.startsWith("github_pat_")) {
    throw new Error("github_secret_binding_wrong_format");
  }
  return token;
}

function scheduledSlot(controller) {
  const daily = controller.cron === DAILY_CRON;
  if (!daily && controller.cron !== INTERVAL_CRON) {
    throw new Error("unapproved_cron");
  }
  const value = controller.scheduledTime;
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error("invalid_scheduled_timestamp");
  }
  const when = new Date(value);
  if (Number.isNaN(when.getTime())) throw new Error("invalid_scheduled_timestamp");
  if (daily) {
    if (when.getUTCMinutes() !== 0 || ![19, 20].includes(when.getUTCHours())) {
      throw new Error("invalid_scheduled_minute");
    }
  } else if (![7, 37].includes(when.getUTCMinutes())) {
    throw new Error("invalid_scheduled_minute");
  }
  when.setUTCSeconds(0, 0);
  const delay = Date.now() - when.getTime();
  if (delay < -60_000 || delay > 18 * 60_000) {
    throw new Error("scheduled_slot_outside_freshness_window");
  }
  if (daily) {
    // BOTH UTC candidates are configured to accommodate Egypt DST.
    // Dispatch ONLY when the authentic Egypt local wall clock is 22:00.
    // The other candidate is deliberately silent. No cost or Gmail activity.
    const localHour = new Intl.DateTimeFormat("en-GB", {
      timeZone: "Africa/Cairo", hour: "2-digit", hourCycle: "h23",
    }).format(when);
    if (localHour !== "22") return null;
  }
  return {
    slot: when.toISOString().replace(".000Z", "+00:00"),
    origin: daily ? DAILY_ORIGIN : INTERVAL_ORIGIN,
  };
}

async function dispatch(controller, env) {
  const event = scheduledSlot(controller);
  if (event === null) {
    console.log("RASD_CLOUDFLARE_DAILY_INACTIVE_CANDIDATE_SKIPPED");
    return;
  }
  const response = await fetch(`${WORKFLOW_URL}/dispatches`, {
    method: "POST",
    headers: {
      ...GH_HEADERS,
      Authorization: `Bearer ${githubToken(env)}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ ref: "main", inputs: event }),
  });
  if (response.status !== 204) {
    throw new Error(`github_workflow_dispatch_http_${response.status}`);
  }
  console.log("RASD_CLOUDFLARE_DISPATCH_ACCEPTED");
}

function safeFailure(error) {
  const known = [
    "unapproved_cron", "invalid_scheduled_timestamp", "invalid_scheduled_minute",
    "scheduled_slot_outside_freshness_window",
    "github_secret_binding_unavailable", "github_secret_binding_nontext",
    "github_secret_binding_too_short", "github_secret_binding_wrong_format",
  ];
  const message = error instanceof Error ? error.message : "";
  return known.includes(message) || /^github_(token_workflow_read|workflow_dispatch)_http_\d{3}$/.test(message)
    ? message : "unexpected_worker_error";
}

export default {
  async fetch() {
    return new Response("Not Found", { status: 404 });
  },
  async scheduled(controller, env, ctx) {
    ctx.waitUntil(dispatch(controller, env).catch(error => {
      console.error(`RASD_CRON_FAILURE_CODE=${safeFailure(error)}`);
      throw error;
    }));
  },
};
