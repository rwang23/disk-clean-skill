# Retention Metadata Contract

## Schema

Each build, release copy, unreferenced image, BuildKit cache, or archived session must have an
associated JSON metadata object. Timestamps use ISO-8601 UTC with a trailing Z. Fields must not
contain tokens, cookies, customer content, or complete session contents.

    {
      "schema_version": 2,
      "kind": "build",
      "state": "failed",
      "owner": "configured-owner",
      "target_path": "<absolute-artifact-path>",
      "run_id": "masked-run-id",
      "started_at": "2026-08-03T23:00:00Z",
      "terminal_at": "2026-08-03T23:12:00Z",
      "created_at": "2026-08-03T23:00:00Z",
      "image_ids": ["sha256:..."],
      "cache_key": "project:branch:masked-sha",
      "retention_class": "failed_build_temp",
      "retention_days": 0,
      "delete_after": "2026-08-03T23:12:00Z",
      "protection_reason": null,
      "release_id": null,
      "readback_ref": null,
      "cleanup_status": null,
      "source": "build-system",
      "content_fingerprint": "optional-sha256-or-manifest-id"
    }

A successful release uses the same schema with state=succeeded and
retention_class=release_image. For a current runtime image or a protected verified external
recovery source, delete_after may be null. When an object is no longer current/last-known-good,
the release workflow must add release_completed_at, evidence that protection was removed, and
delete_after=release_completed_at+5d.

Unreferenced images and BuildKit cache use retention_class=untagged_image or buildkit_cache.
Compute delete_after as created_at/last_used plus 3 days.

Convergence of a successful release project's image uses
retention_class=post_deploy_project_image. This is not an alias for "deployment succeeded, so
delete it." The record must bind release_id, release_completed_at, exact-SHA/readiness/public
readback_ref for the same target, current and protected image IDs, and a verified external
immutable recovery reference. Previous/rollback objects are retained for 5 days after release
completion; ordinary unreferenced build images are retained for 3 days after creation. The
cleanup_status must be SUCCEEDED, SKIPPED, PARTIAL, or FAILED.

Local database backups use retention_class=local_backup and must additionally record:

    {
      "checksum": "sha256:...",
      "checksum_verified_at": "2026-08-03T23:15:00Z",
      "restore_list_verified_at": "2026-08-03T23:16:00Z",
      "offsite_reference": "masked-or-null",
      "delete_after": "2026-08-10T23:15:00Z"
    }

Archived sessions continue to use:

    {
      "schema_version": 2,
      "kind": "archived_session",
      "state": "archived",
      "owner": "configured-owner",
      "target_path": "$SESSION_ARCHIVE_ROOT/example.jsonl",
      "session_id": "masked-session-id",
      "archived_at": "2026-08-03T23:12:00Z",
      "retention_days": 14,
      "delete_after": "2026-08-17T23:12:00Z",
      "source": "session-archive"
    }

Terminal test/tool artifacts use retention_class=temporary_artifact and must include task_id,
terminal_at, owner, delete_after, and protection_reason. They may enter disk-clean's exact
allowlist only after the task is terminal, active process/lock/research-evidence references are
absent, and delete_after has passed. A name containing tmp or cache and directory age cannot
replace metadata.

## Invariants

- Every build must have started_at, terminal_at, state, image_id/image_ids, cache_key, and
  delete_after. If a value is not applicable, write explicit null rather than omitting the field.
- retention_class=failed_build_temp requires state=failed, terminal_at, and
  delete_after=terminal_at.
- A failed build must write terminal metadata and clean regenerable temporary directories in
  finally/always().
- retention_class=temporary_artifact requires terminal state, task_id, terminal_at, owner,
  and delete_after. delete_after must not precede terminal_at; an active task or research
  evidence reference keeps the object protected.
- retention_class=archived_session requires state=archived, an owner matching the configured
  execution identity, session_id, archived_at, and delete_after=archived_at+14d. Active tasks,
  processes, locks, current research evidence, or recovery-chain references exclude the object
  from the allowlist.
- retention_class=local_backup requires checksum, checksum/restore-list verification times,
  backup_chain_role, protected, and an offsite/immutable recovery reference. Latest, rollback,
  or chain-protected nodes must not be deleted. Older nodes enter the exact allowlist only after
  recovery verification is complete and delete_after has passed.
- previous_release/archive_release/history_release delete_after must equal completion time plus
  5 days.
- untagged_image/buildkit_cache delete_after must equal creation or last-use time plus 3 days.
- post_deploy_project_image requires release, readback, protection, and recovery fields. Without
  them, classify it as legacy_unknown or SKIPPED; never infer eligibility from name or disk pressure.
- cleanup_status=SUCCEEDED requires a post-action image inventory and disk readback. If deployment
  succeeded but cleanup or readback failed, use PARTIAL; do not misstate the deployment as FAILED.
- delete_after must equal the relevant state timestamp plus the policy duration; failed builds use
  zero days. The caller may not shorten the policy.
- target_path must be absolute and must match the object represented by the sidecar.
- Missing metadata, invalid JSON, path mismatch, owner mismatch, missing fields, or clock rollback
  classifies the object as legacy_unknown and blocks automatic deletion. A strictly named
  previous-* object may use only the skill's legacy_release_timestamp fallback.
- Missing or incomplete archived-session, local-backup, or temporary-artifact metadata may not be
  upgraded to deletable using a name, directory age, or disk pressure.
- The explicitly caller-supplied session_archive_root is the only permitted legacy session
  fallback root. Only when the first JSONL record has session_meta, payload.id matches the
  filename, the embedded UTC timestamp is older than 14 days, and active/research/recovery
  references are absent may the object be classified as legacy_archived_session and enter the
  platform isolation layer. Other metadata-missing sessions remain legacy_unknown.
- A successful build must never be disguised as a failed build; releases, test evidence, and
  rollback copies use separate categories.

## Placement

Prefer a sidecar next to the artifact:

    <artifact-directory>/.retention.json

When a sidecar is unsuitable, use a machine- or owner-specific directory supplied by the caller:

    Windows: DISK_CLEAN_METADATA_DIR/<run-id>.json
    Linux:   DISK_CLEAN_METADATA_DIR/<run-id>.json
    macOS:   DISK_CLEAN_METADATA_DIR/<run-id>.json

Centralized metadata must still record target_path, owner, and an object fingerprint. After an
object is moved, renamed, or released, update metadata before allowing cleanup to see it.

## State transitions

    build: running -> succeeded
    build: running -> failed -> cleaned
    release: current -> previous -> eligible_after_5d -> deleted
    image/cache: created -> unreferenced -> eligible_after_3d -> pruned
    release image: current -> previous/rollback -> eligible_after_5d -> post_deploy_cleanup -> pruned
    temporary artifact: running -> terminal -> eligible_after_delete_after -> quarantined/deleted
    session: active -> archived -> eligible_after_14d -> deleted
    local backup: created -> checksum/restore_verified -> expired -> eligible_after_delete_after -> deleted

The build workflow cleans a failed build's regenerable temporary directory in finally/always();
disk-clean handles leftover failed objects and metadata. Other historical objects may be deleted or
recycled only by one disk-clean apply run, which records the result. Build or archive workflows
must not delete historical objects independently and claim that retention is complete.
