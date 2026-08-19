# Retention policy

Use UTC state timestamps. Do not replace a known state timestamp with the current file mtime.
Classify candidates in this priority order:

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
9. post_deploy_project_image: release readback succeeds, project ownership and external recovery
   are proven, and only expired unreferenced allowlist image IDs are considered.
10. local_backup: only recovery-verified, explicitly expired, unprotected exact backups.
11. legacy_archived_session: embedded session_meta under the explicitly supplied archive root,
    older than 14 days, no active/research reference, and stable across two inventories;
    prefer platform Trash or same-volume quarantine.
12. legacy_unknown: insufficient evidence; report and do not act.

## Fixed rules

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
  only the legacy fallback; never delete merely because a name contains tmp/cache or because of
  directory age.
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

If real disk pressure remains after the normal 3-day cutoff and regenerable BuildKit/build cache
is the only remaining source, a one-time full cache prune may run only with fresh P3 proof that
the worker is idle, no containers are running, the lock is available, and the user has explicitly
authorized the recovery action. This is a manual recovery action, not a per-project quota. It
must not touch volumes, current images, production containers, databases, or release directories.
