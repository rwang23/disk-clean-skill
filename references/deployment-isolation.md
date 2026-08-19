# Deployment isolation

A normal production release is executed by the project's release workflow and runtime owner.
disk-clean does not start, stop, unregister, merge, or reassign runners, and does not move
builds or deployments to another hosted compute environment. If a release workflow, worker,
fixed gateway transaction, or shared release lock is active, the cleanup batch is SKIPPED.
Regenerable objects may be collected only when the same owner is confirmed, the runner is idle,
the lock is available, and the object remains in the exact allowlist. A container image also
requires exact-revision, runtime, and external readback from the same release transaction;
without readback, do not clean images.

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

See [post-deploy contract](post-deploy-contract.md) for allowlists, protected objects, receipt
fields, and hook installation boundaries.
