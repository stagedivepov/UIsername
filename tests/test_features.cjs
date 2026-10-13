const test = require("node:test");
const assert = require("node:assert/strict");
require("../ui/features-model.js");
const { identitySummary, filterResults } = globalThis.FeaturesModel;
test("identity denominator excludes unknown, errors, auth and suggestion checks", () => {
  const rows = [
    { platform: "Roblox", username: "alpha", status: "AVAILABLE" },
    { platform: "GitHub", username: "alpha", status: "TAKEN" },
    { platform: "Discord", username: "alpha", status: "UNKNOWN" },
    { platform: "Kick", username: "alpha", status: "AUTH_REQUIRED" },
    { platform: "Instagram", username: "alpha", status: "ERROR" },
    { platform: "X", username: "alpha", status: "RATE_LIMITED" },
    { platform: "PlayStation", username: "alpha", status: "UNSUPPORTED" },
    {
      platform: "Roblox",
      username: "alpha7",
      status: "AVAILABLE",
      suggestion: true,
    },
  ];
  const summary = identitySummary(rows);
  assert.equal(summary.available, 1);
  assert.equal(summary.conclusive, 2);
  assert.equal(summary.unresolved, 5);
  assert.equal(summary.singleUsername, true);
});
test("batch consistency uses original input names rather than per-platform normalization", () => {
  const rows = [
    {
      platform: "Roblox",
      username: "Alpha",
      input_username: "Alpha",
      status: "AVAILABLE",
    },
    {
      platform: "GitHub",
      username: "alpha",
      input_username: "Alpha",
      status: "UNKNOWN",
    },
  ];
  assert.equal(identitySummary(rows).singleUsername, true);
  rows.push({ username: "beta", input_username: "Beta", status: "TAKEN" });
  assert.equal(identitySummary(rows).singleUsername, false);
});
test("result filters combine platform, username and explicit state without changing results", () => {
  const rows = [
    { platform: "GitHub", username: "Alpha", status: "TAKEN" },
    { platform: "Roblox", username: "beta", status: "UNKNOWN" },
  ];
  assert.deepEqual(filterResults(rows, "gith", "TAKEN"), [rows[0]]);
  assert.deepEqual(filterResults(rows, "beta", "AVAILABLE"), []);
  assert.equal(rows.length, 2);
});
