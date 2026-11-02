import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { accountStorageKey } from "../lib/account-storage.ts";

test("accounts have separate browser drafts, CVs and preferences", () => {
  for (const suffix of [
    "workspace.v1",
    "cv.workspace.v1",
    "cv.target.v1",
    "discovery.v1",
    "theme",
  ]) {
    assert.notEqual(
      accountStorageKey("alice", suffix),
      accountStorageKey("bob", suffix),
    );
    assert.notEqual(accountStorageKey("alice", suffix), `jobpilot.${suffix}`);
  }
});
import { cvText, fingerprint, safeUrl, monday } from "../lib/workspace.ts";

const profile = JSON.parse(
  readFileSync(new URL("../../fixtures/profile.json", import.meta.url), "utf8"),
);
const draft = {
  job: {
    id: "greenhouse:board:1",
    url: "https://example.org/job",
    description: "Original role",
  },
  cv: cvText(profile),
  letter: "",
  answers: "",
  version: 1,
};
test("CV export preserves source facts and every user-supplied skill", () => {
  const text = cvText({
    ...profile,
    skills: [...profile.skills, "Vue", "Vue.js"],
  });
  assert.ok(text.includes(profile.name));
  for (const e of profile.experience) {
    assert.ok(text.includes(e.company));
    assert.ok(text.includes(e.dates));
  }
  assert.ok(text.includes(profile.education));
  assert.ok(text.includes("Vue · Vue.js"));
});
test("approval fingerprints bind to exact job, CV, letter, answers and version", async () => {
  const original = await fingerprint(draft);
  assert.equal(original, await fingerprint({ ...draft }));
  for (const mutation of [
    { job: { ...draft.job, id: "other" } },
    { job: { ...draft.job, description: "Changed role" } },
    { cv: draft.cv + " edited" },
    { letter: "new letter" },
    { answers: "new answer" },
    { version: 2 },
  ])
    assert.notEqual(original, await fingerprint({ ...draft, ...mutation }));
});
test("outbound links reject executable and invalid URLs", () => {
  assert.equal(safeUrl("javascript:alert(1)"), undefined);
  assert.equal(safeUrl("data:text/html,test"), undefined);
  assert.equal(safeUrl("invalid"), undefined);
  assert.equal(safeUrl("https://example.org/job"), "https://example.org/job");
});
test("weekly metrics start on Monday, including Sunday boundary", () => {
  assert.equal(monday(new Date(2026, 10, 8, 15)).getDate(), 2);
  assert.equal(monday(new Date(2026, 10, 2, 15)).getHours(), 0);
});
