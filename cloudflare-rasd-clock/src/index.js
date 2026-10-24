// RASD Cloudflare Free external clock. It never sees the Gmail or ledger secrets.
// Github accepts only a 204 dispatch from a repo-scoped Actions:write token.
const CRON = "7,37 * * * *";
const OWNER = "Hatem1984";
const REPO = "RASD-Cloud-Monitor";
const WORKFLOW = "rasd-cloudflare-dispatch.yml";
const ORIGIN = "cloudflare-rasd-cron-v1";

function validScheduledSlot(controller) {
  if (controller.cron !== CRON) throw new Error("unapproved_cron");
  if (!Number.isSafeInteger(controller.scheduledTime)) {
    throw new Error("invalid_scheduled_timestamp");
  }
  const stamp = new Date(controller.scheduledTime);
  if (Number.isNaN(stamp.getTime()) ||
      ![7, 37].includes(stamp.getUTCMinutes()) ||
      stamp.getUTCSeconds() !== 0) {
    throw new Error("invalid_scheduled_slot");
  }
  return stamp.toISOString().replace(".000Z", "+00:00");
}

async function dispatch(controller, env) {
  const slot = validScheduledSlot(controller);
  const token = env.GH_ACTIONS_TOKEN;
  if (typeof token !== "string" || token.length < 25) {
    throw new Error("missing_cloudflare_github_token");
  }
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/dispatches`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Accept": "application/vnd.github+json",
      "Authorization": `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "RASD-Cloudflare-Cron/1.0",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      ref: "main",
      inputs: { origin: ORIGIN, slot },
    }),
  });
  // Never log response bodies: they can contain account metadata or details.
  if (response.status !== 204) {
    throw new Error(`github_workflow_dispatch_http_${response.status}`);
  }
  console.log("RASD_CLOUDFLARE_DISPATCH_ACCEPTED");
}

export default {
  async fetch() {
    // Never expose a public endpoint that can trigger mail.
    return new Response("Not Found", { status: 404 });
  },
  async scheduled(controller, env, ctx) {
    ctx.waitUntil(dispatch(controller, env));
  },
};
