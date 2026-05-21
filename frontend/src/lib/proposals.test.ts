import { describe, expect, it } from "vitest";

import {
  actionableChanges,
  filterActionableProposals,
  isActionableProposal,
} from "./proposals";
import type { Proposal } from "./types";

const row = (changes: Proposal["changes"]): Proposal => ({
  id: "refunds:1",
  pattern: "refunds",
  dataset_row_id: "00000000-0000-0000-0000-000000000001",
  row_index: 0,
  dimension_a: "Dog",
  dimension_b: "China",
  dimension_c: "Line",
  changes,
});

describe("actionable proposals", () => {
  it("drops rows where every fix is already at the target value", () => {
    expect(
      isActionableProposal(
        row([{ period: "202403", value_before: 0, value_after: 0 }]),
      ),
    ).toBe(false);
    expect(filterActionableProposals([row([{ period: "202403", value_before: 0, value_after: 0 }])])).toEqual(
      [],
    );
  });

  it("keeps rows with at least one real cell change", () => {
    const p = row([
      { period: "202401", value_before: 0, value_after: 0 },
      { period: "202402", value_before: 200, value_after: 0 },
    ]);
    expect(isActionableProposal(p)).toBe(true);
    expect(actionableChanges(p.changes)).toHaveLength(1);
    expect(filterActionableProposals([p])[0].changes).toHaveLength(1);
  });
});
