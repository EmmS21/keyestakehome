import { fetchProposals } from "./api";
import type { CellChange, CleaningPattern, Proposal } from "./types";

/** Match backend accept no-op tolerance. */
export const VALUE_EPSILON = 1e-9;

export function cellNeedsChange(change: CellChange): boolean {
  return Math.abs(change.value_before - change.value_after) >= VALUE_EPSILON;
}

export function actionableChanges(changes: CellChange[]): CellChange[] {
  return changes.filter(cellNeedsChange);
}

/** Row proposal the server would persist on accept (at least one cell changes). */
export function isActionableProposal(proposal: Proposal): boolean {
  return actionableChanges(proposal.changes).length > 0;
}

export function actionableProposal(proposal: Proposal): Proposal {
  const changes = actionableChanges(proposal.changes);
  return { ...proposal, changes };
}

export function filterActionableProposals(proposals: Proposal[]): Proposal[] {
  return proposals
    .filter(isActionableProposal)
    .map(actionableProposal);
}

/** Scan all server proposals; count rows that would change at least one cell on accept. */
export async function countActionableProposals(
  sessionId: string,
  pattern: CleaningPattern,
): Promise<number> {
  let actionable = 0;
  let offset = 0;
  let total = 0;
  const pageSize = 100;
  do {
    const page = await fetchProposals(sessionId, pattern, pageSize, offset);
    total = page.total_count;
    actionable += filterActionableProposals(page.proposals).length;
    offset += page.proposals.length;
  } while (offset < total);
  return actionable;
}

/** Page through server proposals until `limit` actionable rows or the grid is exhausted. */
export async function fetchActionableProposalsPage(
  sessionId: string,
  pattern: CleaningPattern,
  limit: number,
  startServerOffset: number,
): Promise<{
  proposals: Proposal[];
  session_updated_at: string;
  nextServerOffset: number;
  exhausted: boolean;
}> {
  const out: Proposal[] = [];
  let serverOffset = startServerOffset;
  let sessionUpdatedAt = "";
  let total = Infinity;
  const chunk = Math.max(limit, 50);

  while (out.length < limit && serverOffset < total) {
    const page = await fetchProposals(sessionId, pattern, chunk, serverOffset);
    sessionUpdatedAt = page.session_updated_at;
    total = page.total_count;
    out.push(...filterActionableProposals(page.proposals));
    serverOffset += page.proposals.length;
  }

  return {
    proposals: out.slice(0, limit),
    session_updated_at: sessionUpdatedAt,
    nextServerOffset: serverOffset,
    exhausted: serverOffset >= total,
  };
}
