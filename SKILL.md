---
name: disk-clean
description: >
  Use when the user requests retention cleanup of caller-supplied temporary files, failed builds,
  archived sessions, caches, backups, or release artifacts on Windows, Linux, or macOS. Does not
  apply to analysis-only requests; use storage-analyzer.
---

Treat cleanup as an explicitly authorized, auditable P3 operation. The caller must provide the
platform, target roots, report directory, metadata directory, execution identity, and available
quarantine/recycle adapter. Do not guess paths, usernames, hostnames, or project names. This
skill does not create a persistent runner or delegate deletion to an orchestration system;
build and archive systems only write retention metadata.

Read the directly linked contracts before acting:

- [Retention policy](references/retention-policy.md): category order, retention windows,
  protected objects, and the full-disk-pressure exception.
- [Platform scope and adapters](references/platform-scope-and-adapters.md): caller-supplied
  roots, metadata placement, quarantine interfaces, and action-after evidence.
- [Deployment isolation](references/deployment-isolation.md): release/runtime boundaries and
  post-deploy image cleanup.
- [Legacy fallback and metadata](references/legacy-and-metadata.md): metadata requirements and
  the narrowly scoped legacy rules.
- [Report contract](references/report-contract.md): filenames, timing, required fields, and
  failure states.
- [references/metadata-contract.md](references/metadata-contract.md): metadata schema and
  invariants.
- [references/post-deploy-contract.md](references/post-deploy-contract.md): project-image
  allowlists, receipts, and hook boundaries.

Automatic maintenance is limited to owner-scoped, idle-only official container-runtime
operations and exact job-workspace cleanup. A release transaction's post-deploy finalizer is
the only component that may process expired, unreferenced release artifacts after the same
project and release readback succeeds.

## Non-negotiable safety boundary

- Require an explicit cleanup request and an explicit machine/path boundary.
- Inventory and classify read-only before any apply; show the exact allowlist and dry-run.
- Treat active work, current releases, recovery evidence, databases, volumes, virtual disks,
  user profiles, and uncertain objects as protected or report-only.
- Never delete by age or name alone, use an unchecked root/glob, or widen scope after a failure.
- Use a separate DecisionProof P3 for each independent platform and target root.
- Prefer native Trash/Recycle Bin or same-volume quarantine with a manifest. Count quarantine
  only as quarantined bytes until the user separately authorizes permanent emptying.
- Never stop services, restart the host, restart containers, use global production prune, or
  manually remove containerd, BuildKit, overlayfs, or Docker data directories.
- If identity, ownership, lock, runtime, recovery, category, adapter, or report state is unclear,
  mark the affected candidate or run SKIPPED/PARTIAL and do not guess.

## Output

Every invocation, including dry-run, NO_CHANGE, SKIPPED, PARTIAL, and failed runs, must create
the English and Chinese analysis/cleanup Markdown reports and the self-contained HTML artifact
described in the
[report contract](references/report-contract.md). Use one UTC run_id and never overwrite an
older report. Write the analysis report successfully before apply; write the cleanup report
after direct action-after readback; render the HTML after the final known state. A report or
renderer failure prevents SUCCEEDED and must be recorded in the cleanup receipt.

## Execution gates

1. Confirm the explicit cleanup request, platform, target roots, identity, metadata directory,
   report directory, and quarantine/recycle adapter.
2. Read the metadata contract and relevant retention/deployment references. Establish a separate
   P3 proof for each independent target.
3. Perform a read-only inventory of platform identity, disk revision, capacity, allowed roots,
   state timestamps, metadata, owner, locks, processes, services, releases, and references.
4. Produce the dry-run and analysis report. Only candidates in the exact allowlist with due
   retention, no references or locks, no current-image protection, and complete recovery
   evidence may pass the apply gate.
5. Re-read identity and target revision immediately before each apply batch. Any drift requires
   a new proof; do not continue with stale evidence.

If a gate fails, keep the affected candidate or run report-only and finish with the correct
NO_CHANGE, SKIPPED, PARTIAL, or failed state.

## Workflow

### 1. Inventory

Scan only caller-supplied roots. Record capacity/free space, logical size and file/directory/
reparse counts, absolute paths, state timestamps, metadata, owner, locks/processes, service and
release state, and current references. Do not move or delete during inventory.

### 2. Classify

Apply the priority order in [retention policy](references/retention-policy.md). Keep protected
objects and evidence out of the allowlist. Treat missing or invalid metadata as legacy_unknown
unless the narrowly defined legacy fallback is proven.

### 3. Dry-run

For every candidate, output absolute path, category, state time, delete_after, size, owner,
evidence, protection checks, estimated bytes, and skip reason. Never hide different categories
behind one aggregate.

### 4. Apply

Act only on the confirmed allowlist with complete evidence. Use the platform adapter in
[platform scope and adapters](references/platform-scope-and-adapters.md). Record native
isolation or same-volume quarantine as quarantined; permit permanent deletion only when no
adapter exists, the policy is fully satisfied, and the user explicitly authorizes it.

### 5. Verify, report, and close

Read back from the same target: source-path disappearance, quarantine/original-location
matching, remaining candidates, capacity, and unchanged service/container/release identity.
Record actions, skips, failures, actual reclaimed bytes, rollback, residual risk, and proof
state. Write both language reports, render the HTML with
[scripts/render_report_html.py](scripts/render_report_html.py), and close the P3 proof. Without
action-after readback, do not claim completion.

## Success standard

Success means cleanup was performed safely according to policy and directly verified, not that
the largest possible number of objects was deleted. When disk pressure is high, expand only the
provable scope; never lower the protection boundary.
