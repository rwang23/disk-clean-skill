---
name: disk-clean
description: >
  Use when the user requests retention cleanup of caller-supplied temporary files, failed builds,
  archived sessions, caches, backups, or release artifacts on Windows, Linux, or macOS. Does not
  apply to analysis-only requests; use storage-analyzer.
---

Treat disk cleanup as an explicitly authorized, auditable P3 operation. This skill does not
create a persistent runner or delegate deletion to an orchestration system. When the user
explicitly asks to clean, the assistant runs this specification; build and archive systems
only write retention metadata. The caller must provide the platform, target roots, report
directory, metadata directory, execution identity, and available quarantine/recycle adapters.
The skill must not guess paths, usernames, hostnames, or project names from the machine.
See [references/metadata-contract.md](references/metadata-contract.md) for retention metadata
and [references/post-deploy-contract.md](references/post-deploy-contract.md) for the
post-deploy project-image convergence contract.

Automatic maintenance is limited to owner-scoped, idle-only official container-runtime
operations and exact job-workspace cleanup. A release transaction's own post-deploy finalizer
is the only component that may process expired, unreferenced release artifacts after the same
project and release readback succeeds. These rules do not weaken the P3 authorization boundary.

## Deployment isolation

A normal production release is always executed by the project's release workflow and runtime
owner. disk-clean does not start, stop, unregister, merge, or reassign runners, and does not
move builds or deployments to another hosted compute environment. If a release workflow,
worker, fixed gateway transaction, or shared release lock is active, the cleanup batch is
SKIPPED. Regenerable objects may be collected only when the same owner is confirmed, the
runner is idle, the lock is available, and the object remains in the exact allowlist. A
container image also requires exact-revision, runtime, and external readback from the same
release transaction; without readback, do not clean images.

## Immediate post-deploy convergence

Any project that enables container release convergence must treat cleanup as a separate
post-deploy finalizer:

1. Complete release revision, runtime readiness, and external readback first. Store the
   successful receipt and the externally recoverable source in release evidence. If any
   deployment gate fails, do not clean images.
2. On the same project owner, container runtime, and release lock, run the before check again.
   Read back the current container image ID, last-known-good protection, rollback/evidence
   protection, and candidate image digests. If project ownership, external recovery, or
   absence of container references cannot be proven, mark the candidate SKIPPED.
3. Process only post_deploy_project_image candidates in the caller-supplied project allowlist:
   previous/rollback images older than 5 days after release_completed_at, or explicitly
   unreferenced images older than 3 days after created_at. Current image, last-known-good,
   active rollback, volume, container, database, and release directories never enter this batch.
4. Call only the exact image-ID deletion interface for the matching runtime. Never use global
   image/system/volume prune and never remove containerd, overlayfs, or layer data manually.
5. Cleanup failure does not roll back an already verified service, but the deployment receipt
   must be PARTIAL and include candidates, completed actions, skip reasons, and the next retry
   time. Only successful cleanup action-after readback may be marked SUCCEEDED.

See [references/post-deploy-contract.md](references/post-deploy-contract.md) for allowlists,
protected objects, receipt fields, and hook installation boundaries.

## Report contract for every run

Every invocation of this skill must create one disk analysis report and one cleanup report,
including dry-run, NO_CHANGE, SKIPPED, PARTIAL, and failed runs. Use a UTC run_id in every
filename and never overwrite an older report. The caller supplies the output directory through
report_dir or DISK_CLEAN_REPORT_DIR. The five audit outputs are:

- disk-analysis-<run_id>.en.md: written after inventory/classify and before any apply. If this
  write fails, do not apply and mark the run SKIPPED.
- disk-analysis-<run_id>.zh-CN.md: the Chinese companion for the same analysis dataset.
- disk-cleanup-<run_id>.en.md: written after action-after readback; contains final proof,
  actual actions, and residual risk. If this write fails, the run cannot be SUCCEEDED and is
  at least PARTIAL.
- disk-cleanup-<run_id>.zh-CN.md: the Chinese companion for the same cleanup dataset.
- disk-clean-report-<run_id>.html: a self-contained Apple-style web report that summarizes the
  analysis and cleanup records, complete candidate manifest, protection and skip reasons,
  evidence, rollback, and receipt/proof. It must not depend on a CDN, external fonts, or the
  network; it must preserve every manifest row and the complete source Markdown/JSON. For an
  apply run, generate it after action-after. For dry-run, SKIPPED, and NO_CHANGE, generate it
  after the final known state. Default the page to English with a Chinese language switch, and
  never overwrite an older page.

The web page is a presentation layer for the audit Markdown and must not change the cleanup
conclusion. Use [scripts/render_report_html.py](scripts/render_report_html.py) as the standard
library renderer. A rendering failure must be written to the cleanup receipt, and the run must
be at least PARTIAL; never claim that the web report is complete.

The analysis report must include at least run_id, policy version, host/identity, target scope,
total/used/free disk capacity, logical size/file/directory/reparse counts for every allowed
root, metadata/owner/lock/process references, absolute candidate path, category, status time,
delete_after, size, evidence, protected objects, dry-run estimate, skip reason, and DecisionProof
state. The cleanup report must include candidates, quarantined, deleted, skipped, failed,
estimated_bytes, quarantined_bytes, reclaimed_bytes, direct action-after readback, proof state,
cleanup receipt, rollback, and residual risk.

The report directory, report files, DecisionProof, and cleanup receipt are protected evidence,
not candidates. Exclude the report currently being generated and historical reports in that
directory from scanning. reclaimed_bytes may come only from direct post-cleanup capacity
readback on the same volume. The logical size in the Windows Recycle Bin, Linux desktop
Trash, macOS Trash, or same-volume quarantine counts only as quarantined_bytes.

## Fixed policies

Use UTC state timestamps. Do not replace a known state timestamp with the current file mtime:

- failed_build_temp: retain for zero days. Once a build reaches a failed terminal state, clean
  regenerable temporary directories immediately; metadata delete_after equals terminal_at.
  Do not touch running, process-referenced, or unproven failed-build objects.
- security_scan_builder: retain for zero days. Security scans must use a job-scoped BuildKit
  builder; delete the builder and scan images in finally/always() even when the scan fails.
- previous_release, archive_release, history_release: retain for 5 days from archived_at,
  release_completed_at, or a strictly parsed release timestamp. Protect the current release,
  current runtime image, most recent verified external recovery source, and active transaction.
- untagged_image: reclaim only through the official Docker prune interface after created_at is
  older than 3 days, with no container reference and no current/last-known-good protection.
- rootless_helper_image: when the project-specific rootless daemon has no running containers,
  the image is not the production current image, and it is older than 3 days, reclaim pullable
  helper/tool images on that owner's socket with docker image prune --all. This rule does not
  apply to a rootful production daemon.
- buildkit_cache: when the runner is idle and last_used is older than 3 days, reclaim through
  docker builder prune or docker buildx prune on the matching rootless daemon. Never delete
  BuildKit, containerd, overlayfs, or rootless Docker data directories manually.
- runner_job_workspace: after a job reaches a terminal state, reclaim only an exact repository
  checkout/workspace allowlist such as /srv/actions-runner/*/_work/<repo>. Do not include
  runner installation, _tool, unknown paths, or Docker data directories.
- current_running_image: never delete automatically. Read the current digest and container
  reference from the same runtime first.
- rollback_release: do not retain forever. Delete a local unreferenced old rollback/release
  object only when the current image and at least one verified external recovery source remain.
- post_deploy_project_image: produced only by a successful release finalizer. Bind it to
  release_id/release_completed_at, exact-SHA readback, project allowlist, current and
  last-known-good image IDs, and an external immutable recovery reference. Previous/rollback
  objects default to 5 days; ordinary unreferenced build images default to 3 days. Never use
  global rootful prune.
- local_backup: disk-clean does not create local backups. JIT backups required by deployment
  remain the release workflow's responsibility. For cleanup, each owner/project must retain
  the newest backup that passed checksum, restore-list, and offsite/immutable recovery checks,
  plus nodes explicitly marked protected in the backup chain. An older backup may enter the
  exact allowlist only when recovery checks are complete, delete_after is valid and expired,
  and it is no longer latest/rollback/chain protected. If recovery checks are absent, the chain
  role is unclear, or the newest backup is incomplete, report the whole chain and do not delete.
- temporary_artifact: metadata must mark a terminal temporary test/tool output and provide
  owner, terminal_at, delete_after, and retention_class=temporary_artifact. Clean only after
  expiry and after task/process/research-evidence references are absent. Without metadata, use
  only the legacy fallback below; never delete merely because a name contains tmp/cache or
  because of directory age.
- archived_session: metadata must have state=archived, an owner matching the configured
  execution identity, archived_at, session_id, and delete_after=archived_at+14d. The session
  must be absent from active tasks, processes, locks, current research evidence, and recovery
  chains, and delete_after must be due before it enters the allowlist. Prefer the platform
  Trash/Recycle Bin or same-volume quarantine. Missing metadata, owner mismatch, or unclear
  identity is legacy_unknown and report-only. Only an explicitly caller-supplied session archive
  root may use the legacy_archived_session fallback for parseable embedded session_meta.
- Databases, Docker volumes, virtual disks, and user profiles are not deleted by ordinary age rules.
- Historical objects without valid metadata are legacy_unknown. Only explicitly marked failed
  builds or terminal temporary artifacts that meet the legacy fallback may become low-confidence
  candidates. Historical local backups, releases, and images are never auto-deleted. Embedded
  session_meta is eligible for legacy_archived_session only under the explicitly supplied archive
  root.

If real disk pressure remains after the normal 3-day cutoff and regenerable BuildKit/build
cache is the only remaining source, a one-time full cache prune may run only with fresh P3 proof
that the worker is idle, no containers are running, the lock is available, and the user has
explicitly authorized the recovery action. This is a manual recovery action, not a per-project
quota. It must not touch volumes, current images, production containers, databases, or release
directories.

## Execution gates

1. The user explicitly requests cleanup and the target machine/path boundary is explicit.
2. Begin with a read-only scan of platform identity, disk revision, candidate list, and estimated
   reclaimed space.
3. Create a separate DecisionProof P3 for every independent platform/target root; never merge
   multiple targets into one ambiguous target.
4. Read [references/metadata-contract.md](references/metadata-contract.md) and verify candidate
   state, timestamps, owner, and protection fields.
5. Produce the dry-run first. Before any apply, successfully write
   disk-analysis-<run_id>.en.md into the protected report directory. Only candidates in the
   allowlist with delete_after <= now, no references, no lock, no current-image protection,
   and no incomplete recovery verification may enter apply. If the analysis write fails, do not
   apply and mark the run SKIPPED.

If identity, owner, runtime state, rollback/backup boundary, or candidate category is unclear,
stop that candidate and report SKIPPED. Do not widen the path or fall back to whole-disk
age-based deletion.

## Machine layout

Prefer sidecar metadata next to the target object so metadata and object lifecycles remain
aligned. When a sidecar is unsuitable, use the caller-provided metadata_dir or
DISK_CLEAN_METADATA_DIR and record the absolute target path. The following platform examples
are conventions, not auto-discovery or authorization to expand scope:

| Platform | Metadata directory | Main permitted object scope |
| --- | --- | --- |
| Windows | DISK_CLEAN_METADATA_DIR or caller-provided directory | TEMP and explicit application temporary/archive namespaces |
| Linux | DISK_CLEAN_METADATA_DIR or $XDG_STATE_HOME/disk-clean/metadata | TMPDIR and explicit application temporary/archive namespaces |
| macOS | DISK_CLEAN_METADATA_DIR or ~/Library/Application Support/disk-clean/metadata | TMPDIR and explicit application temporary/archive namespaces |

Never expand scope merely because a directory name contains temp, archive, backup, or session.

## Workflow

### 1. Inventory

Record hostname, connection identity, disk capacity/free space, target paths, file sizes,
state timestamps, metadata, owner, lock/process references, current release, and service state
for each machine. Inventory is read-only; do not move or delete first.

### 2. Classify

Classify in this priority order:

1. protected_active: running, being written, referenced by a service/process, current release,
   or current research task.
2. protected_backup: database backup, rollback bundle, SQLite/WAL/SHM, Docker volume, or VHDX.
3. failed_build_temp: metadata-backed failed build with delete_after <= now; no retention.
4. temporary_artifact: complete terminal metadata, due delete_after, and no active reference.
5. archived_session: the 14-day rule passes and owner/identity/activity checks pass.
6. previous_release/archive_release: the 5-day rule passes and it is not current/last-known-good.
7. security_scan_builder/runner_job_workspace: terminal job, matching owner, idle worker, and
   exact job/target allowlist only.
8. untagged_image/rootless_helper_image/buildkit_cache: 3-day rule, no references, idle worker,
   and the matching runtime's official interface; no global prune on production runtime.
9. post_deploy_project_image: release readback succeeds, project ownership and external
   recovery are proven, and only expired unreferenced allowlist image IDs are considered.
10. local_backup: only recovery-verified, explicitly expired, unprotected exact backups.
11. legacy_archived_session: embedded session_meta under the explicitly supplied archive root,
    older than 14 days, no active/research reference, and stable across two inventories;
    prefer platform Trash or same-volume quarantine.
12. legacy_unknown: insufficient evidence; report and do not act.

### 3. Dry-run

For every candidate, output absolute path, category, state time, delete_after, size, owner,
evidence, protection checks, estimated reclaim, and skip reason. Never hide different
categories behind one aggregate.

### 4. Before gate

Before each apply batch, reread identity and revision for the same target and run DecisionProof
before. Check locks, processes, services, current release, realpath, symlink/reparse points,
permissions, and that the target remains in the allowlist. Any drift requires new proof; do
not continue with an old proof.

### 5. Apply

Act only on candidates explicitly authorized and with complete rule evidence. On Windows, Linux,
and macOS, prefer the platform-native Trash/Recycle Bin; on headless systems or without a
native adapter, use same-volume quarantine with a manifest. Record the result as quarantined:
quarantine still consumes source-volume space, so count it only as quarantined_bytes until the
user separately authorizes permanent emptying. Permanent deletion is allowed only when no
platform adapter exists, the target fully satisfies the policy, and the user explicitly
authorizes it; record it as deleted. Never:

- run rm -rf or Remove-Item -Recurse over an unexpanded/unchecked glob, root, or entire Temp;
- delete active objects in a sessions directory;
- delete backups, databases, Docker volumes, VHDX, or unknown releases;
- stop services, restart the host, or restart containers to release space;
- expand to a sibling directory because one candidate failed.

The platform adapter must declare and verify:

| Platform | Preferred isolation | Direct action-after evidence |
| --- | --- | --- |
| Windows | Native Recycle Bin or Shell API | source path gone, original-location match, isolation manifest readback |
| Linux | desktop Trash API; same-volume quarantine when headless | source path gone, quarantine manifest, same-volume capacity readback |
| macOS | Native Trash or Finder API; same-volume quarantine without UI | source path gone, Trash/quarantine manifest, same-volume capacity readback |

If the platform adapter, isolation location, or recovery method is unclear, mark the candidate
SKIPPED; never downgrade to direct deletion.

### 6. Verify, report, and close

Read back directly from the same target: whether candidate paths disappeared, remaining
candidate count/size, free disk space, and whether service/container/release identity changed.
Record deleted, skipped, failed, actual reclaimed space, and residual risk. Write
disk-cleanup-<run_id>.en.md and its Chinese companion, render
disk-clean-report-<run_id>.html, and then finish with DecisionProof close. Without action-after
readback, do not claim completion. The web page must show summary cards, capacity, categories,
allowed roots, the complete candidate manifest, protected/skipped objects, evidence chain,
rollback notes, and the complete source text of both Markdown reports plus receipt/proof.
If the cleanup report or web page fails to write, mark the run at least PARTIAL, never
SUCCEEDED; include reports, page, proof, and paths in the cleanup receipt.

## Legacy fallback

Only metadata-missing failed builds or terminal temporary directories may use the legacy
fallback, and all of the following must hold:

- the object is under an explicit allowlist;
- the name clearly contains a failed/temporary marker such as failed, partial, probe, cleanup,
  or test, or it is an explicit build failure log (*.err.log, *.error.log, or a build-error name);
- its last write is older than 3 days;
- it exists with stable size across two inventories;
- no process, service, release, or task references it;
- it contains no backup, database, user profile, or current test evidence;
- the dry-run labels it separately as legacy_fallback.

For previous-* release directories, only a directory with a parseable UTC release timestamp,
outside the current release path, with no process/mount/service reference and stable size across
two inventories may be labeled legacy_release_timestamp in dry-run. Do not use ordinary mtime
as a state timestamp. Metadata-missing historical archives/sessions, local backups, images,
and unclear temporary objects are report-only.

### Archived-session legacy fallback

Only the explicitly caller-supplied session_archive_root may use this fallback. Each file must
be JSONL, its first record must have type=session_meta, payload.id must match the session ID in
the filename, and its embedded UTC timestamp must be older than the 14-day cutoff. The file
must have stable size across two inventories and be readable exclusively; its session ID must
not appear in active tasks, current research evidence, recovery chains, or this run's report/
proof. Only then may it be labeled legacy_archived_session and enter the platform isolation
layer. Any failed check is legacy_unknown. Do not apply this fallback to other archive/session
directories and do not substitute file mtime for the embedded timestamp.

## Build and archive write requirements

All new build and archive workflows must write metadata at each state transition. At minimum,
write:

- started_at, terminal_at, state, owner, and run_id;
- image_id/image_ids when an image is produced, cache_key, and target_path;
- delete_after, retention_class, and protection_reason;
- temporary_artifact also requires task_id, terminal_at, owner, and delete_after not earlier
  than terminal state; archived_session requires state=archived, session_id, archived_at, and
  delete_after=archived_at+14d;
- post-deploy cleanup also requires release_id, release_completed_at, readback_ref,
  current_image_ids, protected_image_ids, external_recovery_ref, and cleanup_status.

State transitions:

- build starts: running;
- build succeeds: succeeded, then follow release/evidence policy;
- build fails: write terminal_at and delete_after=terminal_at, and clean the temporary directory
  in finally/always();
- security scan: write a unique cache_key and builder record, then delete the job-scoped
  builder, scan image, and temporary workspace at terminal state;
- previous/archive/history completion: write archived_at or release_completed_at and delete_after +5d;
- unreferenced image or BuildKit cache: write created_at/last_used and delete_after +3d;
- project-image cleanup after a successful release: write retention_class=post_deploy_project_image,
  delete_after, readback and protected image IDs; if action-after fails, keep metadata with
  partial status and never present it as a failed deployment or successful deletion;
- local backup: write checksum, restore-list result, offsite/immutable recovery reference,
  backup_chain_role, protected, and delete_after; without recovery evidence or a clear chain role,
  do not auto-delete;
- terminal temporary artifact: write retention_class=temporary_artifact, task reference,
  and terminal time;
- archived session: write state=archived, owner, session identity, archived_at, and the
  14-day delete_after, and keep it protected while active tasks still reference it.

Invalid metadata, time reversal, target-path changes, owner mismatch, or inconsistent state are
report-only.

A platform idle-maintenance timer may call the official 72-hour builder/cache prune when the
same owner's worker is idle, no containers are running, and the shared release lock is
available, and may delete explicitly listed job workspaces. The timer must not run a global
prune on a production runtime, delete volumes, or remove the runner toolchain or installation.

## Output format

Every run must retain two non-overwriting Markdown reports and one non-overwriting HTML page
using the same UTC run_id:

- disk-analysis-<run_id>.en.md: English inventory/classify/dry-run and pre-apply analysis;
- disk-analysis-<run_id>.zh-CN.md: Chinese analysis for the same dataset;
- disk-cleanup-<run_id>.en.md: English post-apply action-after, cleanup action, rollback, and
  residual-risk report;
- disk-cleanup-<run_id>.zh-CN.md: Chinese cleanup report for the same dataset;
- disk-clean-report-<run_id>.html: self-contained Apple-style read/filter/print page that
  aggregates both Markdown reports, the complete manifest, every protection/skip reason,
  receipt, DecisionProof, and rollback information.

Both Markdown reports must contain at least run_id, policy_version, host, target_key,
observed_at, proof_state, and evidence_refs. The analysis report must also contain every
candidate's absolute path, category, state time, delete_after, size, owner, metadata,
reference/lock checks, protected objects, estimated_bytes, skipped items, and apply allowlist.
The cleanup report must also contain candidates, quarantined, deleted, skipped, failed,
estimated_bytes, quarantined_bytes, reclaimed_bytes, direct action-after readback,
cleanup_status, cleanup_receipt, rollback, and residual_risk.

Report paths, DecisionProof, and cleanup receipt must cross-reference one another. A failed
analysis write must prevent apply, and a failed cleanup or HTML write must prevent SUCCEEDED.
HTML must not truncate the candidate table or replace the source text with a summary; search
and filtering only change visual display and never remove or change the underlying records.

The success standard is "cleaned safely according to policy and verified", not "deleted as
much as possible". When disk pressure is high, expand only the provable scope; never lower
the protection boundary.
