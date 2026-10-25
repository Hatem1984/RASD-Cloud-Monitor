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

test("one-minute diagnostic is rejected and cannot reach GitHub", async () => {
  const errors = [];
  const requests = [];
  globalThis.fetch = async (url, opts) => {
    requests.push({ url, opts });
    return { status: 204 };
  };
  console.error = (message) => errors.push(message);
  try {
    await assert.rejects(invoke({ cron: "* * * * *", scheduledTime: Date.now() }));
    assert.equal(requests.length, 0);
    assert.ok(errors.some(x => x.includes("unapproved_cron")));
    assert.ok(!errors.join("").includes(token));
  } finally { globalThis.fetch = oldFetch; console.error = oldError; }
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

test("daily Cairo 22:00 dispatch matches BOTH DST seasons and only one UTC candidate", async () => {
  const captured = [];
  globalThis.fetch = async (url, options) => {
    captured.push(JSON.parse(options.body).inputs);
    return { status: 204 };
  };
  const cases = [
    { active: "2026-07-05T19:00:00Z", inactive: "2026-07-05T20:00:00Z" },
    { active: "2026-12-05T20:00:00Z", inactive: "2026-12-05T19:00:00Z" },
  ];
  try {
    for (const sample of cases) {
      Date.now = () => Date.parse(sample.active) + 90_000;
      await invoke({ cron: "0 19,20 * * *", scheduledTime: Date.parse(sample.active) });
      assert.equal(captured.at(-1).origin, "cloudflare-rasd-daily-v1");
      assert.equal(captured.at(-1).slot, sample.active.replace(".000Z", "+00:00").replace("Z", "+00:00"));
      const before = captured.length;
      Date.now = () => Date.parse(sample.inactive) + 90_000;
      await invoke({ cron: "0 19,20 * * *", scheduledTime: Date.parse(sample.inactive) }, {});
      assert.equal(captured.length, before, "inactive 19/20 candidate may not dispatch");
    }
    assert.equal(captured.length, 2);
  } finally { Date.now = oldNow; globalThis.fetch = oldFetch; }
});

test("invalid daily minute, wrong UTC hour and stale daily event cannot call GitHub", async () => {
  const called = [];
  globalThis.fetch = async (...args) => { called.push(args); return { status: 204 }; };
  try {
    Date.now = () => Date.parse("2026-12-05T20:02:00Z");
    for (const time of ["2026-12-05T20:01:00Z", "2026-12-05T18:00:00Z"]) {
      await assert.rejects(invoke({ cron: "0 19,20 * * *", scheduledTime: Date.parse(time) }));
    }
    Date.now = () => Date.parse("2026-12-05T20:25:00Z");
    await assert.rejects(invoke({ cron: "0 19,20 * * *", scheduledTime: Date.parse("2026-12-05T20:00:00Z") }));
    assert.equal(called.length, 0);
  } finally { Date.now = oldNow; globalThis.fetch = oldFetch; }
});
