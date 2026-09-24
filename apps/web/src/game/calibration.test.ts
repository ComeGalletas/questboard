import { test } from "node:test";
import assert from "node:assert/strict";
import { calibration, estimateHint } from "./calibration.ts";
import { at, quest } from "./fixtures.ts";

const now = at("2026-09-25", 12);
const done = (category: "learning" | "health", est: number, actual: number, day = "2026-09-20") =>
  quest({
    category,
    estimate_min: est,
    actual_min: actual,
    status: "done",
    completed_at: `${day}T15:00:00Z`,
  });

test("median ratio per category, needs 3 samples, recent only", () => {
  const qs = [
    done("learning", 30, 45),
    done("learning", 60, 90),
    done("learning", 20, 60),
    done("health", 30, 30),
    done("learning", 30, 300, "2026-08-01"),
  ];
  assert.deepEqual(calibration(qs, now), { learning: { ratio: 1.5, samples: 3 } });
});

test("hints only when the estimate is clearly off", () => {
  const cal = { learning: { ratio: 1.5, samples: 3 }, health: { ratio: 1.05, samples: 4 } };
  assert.equal(
    estimateHint(cal, "learning", 30),
    "You usually take about 1.5× your estimate for learning — about 45 min.",
  );
  assert.equal(estimateHint(cal, "health", 30), null);
  assert.equal(estimateHint(cal, "jobs", 30), null);
});
