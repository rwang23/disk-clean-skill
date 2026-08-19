# Post-deploy retention contract

This reference defines the optional cleanup boundary that runs after a successful
containerized release. It is platform-neutral and project-scoped. The release
workflow owns deployment; `disk-clean` only inspects and removes exact, caller-
authorized artifacts after the release transaction has produced decisive evidence.

## Gate order

The finalizer is eligible only after the same release transaction has completed all
of the following on the matching host and runtime:

1. The source revision and every production image reference are exact and digest-qualified.
2. Runtime container image IDs, revision labels, migration/readiness state, and service health
   have been read back from the live project.
3. A project-owned external endpoint or equivalent release surface reads back the target revision.
4. The transaction has written its committed receipt, just-in-time backup evidence, and at least
   one verified external immutable recovery reference.

If any deployment gate fails, the finalizer is not called. If deployment is verified but the
finalizer fails, deployment remains `deployed` and cleanup is reported as `PARTIAL`; it must not
silently roll back a healthy service.

## Caller-supplied allowlist

The allowlist is data, not discovery. A finalizer must receive an explicit record for each project
or runtime boundary and reject anything not present in it:

| Field | Required boundary |
|---|---|
| `project` | Stable project identifier supplied by the release owner |
| `owner` | Exact owner identity that holds the release lock |
| `runtime` | Docker, Podman, or another reviewed compatible runtime |
| `runtime_scope` | Exact daemon/socket/context or equivalent runtime boundary |
| `repository_allowlist` | Exact image repositories or immutable artifact namespaces |
| `release_evidence_ref` | Receipt containing revision, readiness, and external readback |

Unknown projects, repositories, image prefixes, runtimes, sockets, or paths are
`legacy_unknown` and are reported without deletion.

## Protected objects

Before inventory, the finalizer reads and records:

- current container IDs and image IDs for every production service;
- the target revision and digest that passed readback;
- last-known-good and active rollback image IDs from the transaction receipt/journal;
- the immutable registry digest or other external recovery reference for every image;
- release completion time and shared release lock state;
- volumes, bind mounts, databases, release directories, and backup evidence.

Any image ID that is current, last-known-good, referenced by a container, held by an active rollback
transaction, or missing a verified external recovery reference is protected. Protected objects stay
outside the cleanup allowlist even when their names look old.

## Eligibility and action

An artifact may enter the dry-run allowlist only when all checks pass:

- its repository/namespace is in the caller-supplied allowlist;
- it has no direct container or service reference;
- it is not current, last-known-good, or an active rollback ID;
- its digest is immutable and externally recoverable, or the release evidence names another verified
  recovery source;
- `created_at`/`release_completed_at` satisfies the class cutoff: three days for an unreferenced
  build artifact, five days for a previous/rollback release artifact;
- the same owner can acquire the shared release lock and no release worker is active.

Apply uses exact image IDs or artifact IDs from that dry-run list and the runtime's official removal
interface. It never uses a global image/system/volume prune, a wildcard path, or direct deletion under
containerd, overlayfs, BuildKit, or runtime data roots. A refused artifact is `SKIPPED`, not a reason
to broaden the list.

## Receipt and metadata

The finalizer writes one owner-scoped `post_deploy_cleanup` record beside the release receipt or
under the caller-provided metadata directory. It must include:

```text
run_id, release_id, project, owner, host, platform, runtime, policy_version
release_completed_at, readback_ref, current_image_ids, protected_image_ids
candidate_image_ids, deleted_image_ids, skipped_image_ids, failed_image_ids
external_recovery_ref, estimated_bytes, quarantined_bytes, reclaimed_bytes
cleanup_status, proof_state, evidence_refs, residual_risk
```

`cleanup_status` is one of `SUCCEEDED`, `SKIPPED`, `PARTIAL`, or `FAILED`.
`SUCCEEDED` requires an action-after image inventory and disk readback. `SKIPPED` means there was
no eligible candidate or a safety guard declined the batch. `PARTIAL` means deployment readback
passed but one or more cleanup actions or readbacks failed. `FAILED` is reserved for a finalizer
that could not establish its identity/before gate; it must leave all candidates untouched.

## Hook boundary and rollout

The hook is invoked by the release gateway or by the transaction that already owns the exact release
lock. CI must not receive a generic privileged runtime socket or implement this policy with an ad-hoc
remote shell command. A host must have the reviewed helper installed and its allowlist/version read
back before a workflow starts depending on the cleanup receipt.

Installing a helper, changing a runtime scope, adding a repository, or enabling a new host is a
separate P3 operation: dry-run, gateway/permission review, controlled canary, direct service/image/
disk readback, then enablement for the remaining allowlisted targets.
