import assert from "node:assert/strict";
import test from "node:test";
import worker from "./src/index.js";

const token = "github_pat_" + "x".repeat(72);
const config = { GH_ACTIONS_TOKEN: token };
const oldFetch = globalThis.fetch;
const oldNow = Date.now;
const oldLog = console.log;
const oldError = console.error;

async function invoke(controller, env = config) {
  let pending;
  await worker.scheduled(controller, env, {
    waitUntil(p) { pending = p; },
  });
  assert.ok(pending, "worker must register the scheduled task");
  await pending;
}

test("temporary diagnostic only GETs GitHub workflow and cannot mail", async () => {
  const requests = [];
  const logs = [];
  globalThis.fetch = async (url, opts) => {
    requests.push({ url, opts });
    return { status: 200 };
  };
  console.log = (message) => logs.push(message);
  try {
    await invoke({ cron: "* * * * *", scheduledTime: Date.now() });
    assert.equal(requests.length, 1);
    assert.match(requests[0].url, /rasd-cloudflare-dispatch.yml$/);
    assert.equal(requests[0].opts.method, undefined);
    assert.ok(logs.includes("RASD_GITHUB_TOKEN_WORKFLOW_READ_HTTP_200"));
    assert.ok(!logs.join("").includes(token));
  } finally { globalThis.fetch = oldFetch; console.log = oldLog; }
});

test("valid main cron sends one bounded protected dispatch, no token logs", async () => {
  const requests = [];
  Date.now = () => Date.parse("2026-10-24T17:39:10Z");
  globalThis.fetch = async (url, options) => {
    requests.push({ url, options });
    return { status: 204 };
  };
  const logs = [];
  console.log = (value) => logs.push(value);
  try {
    await invoke({
      cron: "7,37 * * * *",
      scheduledTime: Date.parse("2026-10-24T17:37:28Z"),
    });
    assert.equal(requests.length, 1);
    assert.equal(requests[0].options.method, "POST");
    const body = JSON.parse(requests[0].options.body);
    assert.equal(body.ref, "main");
    assert.equal(body.inputs.slot, "2026-10-24T17:37:00+00:00");
    assert.equal(body.inputs.origin, "cloudflare-rasd-cron-v1");
    assert.ok(logs.includes("RASD_CLOUDFLARE_DISPATCH_ACCEPTED"));
    assert.equal((await worker.fetch()).status, 404);
  } finally { Date.now = oldNow; globalThis.fetch = oldFetch; console.log = oldLog; }
});

test("fail closed on invalid cron, old slot, missing secret", async () => {
  Date.now = () => Date.parse("2026-10-24T17:39:00Z");
  const errors = [];
  console.error = (message) => errors.push(message);
  globalThis.fetch = async () => { throw Error("fetch must not run"); };
  try {
    await assert.rejects(invoke({
      cron: "7,37 * * * *",
      scheduledTime: Date.parse("2026-10-24T17:07:00Z"),
    }));
    await assert.rejects(invoke({
      cron: "7,37 * * * *",
      scheduledTime: Date.parse("2026-10-24T17:38:00Z"),
    }));
    await assert.rejects(invoke({
      cron: "7,37 * * * *",
      scheduledTime: Date.parse("2026-10-24T17:37:00Z"),
    }, {}));
    assert.ok(errors.some(x => x.includes("scheduled_slot_outside_freshness_window")));
    assert.ok(errors.some(x => x.includes("invalid_scheduled_minute")));
    assert.ok(errors.some(x => x.includes("github_secret_binding_unavailable")));
    assert.ok(!errors.join("").includes(token));
  } finally { Date.now = oldNow; globalThis.fetch = oldFetch; console.error = oldError; }
});
