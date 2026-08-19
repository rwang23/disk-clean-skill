# Legacy fallback and metadata

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
two inventories may be labeled legacy_release_timestamp in dry-run. Do not use ordinary mtime as
a state timestamp. Metadata-missing historical archives/sessions, local backups, images, and
unclear temporary objects are report-only.

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
- security scan: write a unique cache_key and builder record, then delete the job-scoped builder,
  scan image, and temporary workspace at terminal state;
- previous/archive/history completion: write archived_at or release_completed_at and delete_after
  +5d;
- unreferenced image or BuildKit cache: write created_at/last_used and delete_after +3d;
- project-image cleanup after a successful release: write retention_class=post_deploy_project_image,
  delete_after, readback and protected image IDs; if action-after fails, keep metadata with partial
  status and never present it as a failed deployment or successful deletion;
- local backup: write checksum, restore-list result, offsite/immutable recovery reference,
  backup_chain_role, protected, and delete_after; without recovery evidence or a clear chain role,
  do not auto-delete;
- terminal temporary artifact: write retention_class=temporary_artifact, task reference, and
  terminal time;
- archived session: write state=archived, owner, session identity, archived_at, and the 14-day
  delete_after, and keep it protected while active tasks still reference it.

Invalid metadata, time reversal, target-path changes, owner mismatch, or inconsistent state are
report-only.

A platform idle-maintenance timer may call the official 72-hour builder/cache prune when the
same owner's worker is idle, no containers are running, and the shared release lock is available,
and may delete explicitly listed job workspaces. The timer must not run a global prune on a
production runtime, delete volumes, or remove the runner toolchain or installation.
