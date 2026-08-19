# Disk Clean

Safe, evidence-first retention cleanup for Windows, Linux, and macOS.

`disk-clean` is a high-permission cleanup skill for an assistant or automation
host. It turns a user-authorized cleanup into a bounded, reviewable transaction:
inventory, classify, dry-run, exact allowlist, before gate, quarantine/delete,
action-after readback, and bilingual reporting.

中文说明见 [README.zh-CN.md](README.zh-CN.md)。

## What it does

- Finds only caller-supplied target roots; it never discovers a user's private
  folders by guessing names, usernames, hosts, or projects.
- Handles failed builds, terminal temporary artifacts, archived sessions,
  verified old backups, cache, release artifacts, and optional post-deploy
  container artifacts.
- Preserves active work, current releases, recovery evidence, databases,
  volumes, virtual disks, unknown paths, and incomplete metadata chains.
- Uses a platform-native Trash/Recycle Bin or a same-volume quarantine before
  permanent deletion whenever the platform adapter supports it.
- Reports quarantined bytes separately from permanently reclaimed bytes.

## Platform boundary

Every run must receive an explicit configuration object containing at least:

```yaml
platform: windows | linux | macos
target_roots:
  - <absolute-root-1>
  - <absolute-root-2>
report_dir: <absolute-report-directory>
metadata_dir: <absolute-metadata-directory>
actor: <configured-owner>
quarantine: native-trash | same-volume-quarantine
```

The package does not assume a fixed home directory, drive letter, temporary
folder, session archive, project, cloud host, container socket, or username.
Platform conventions such as `%TEMP%`, `$TMPDIR`, and `$XDG_CACHE_HOME` may be
used only when the caller resolves them into an explicit allowlist before the
run.

## Retention rules

The default policy is deliberately conservative:

- failed builds: terminal metadata and `delete_after=terminal_at`;
- terminal temporary artifacts: complete owner/task/terminal metadata and an
  expired `delete_after`;
- archived sessions: `state=archived`, matching owner/session identity, and
  `delete_after=archived_at+14d`;
- previous/archive/history release artifacts: five days after the recorded
  release state time;
- unreferenced build images and cache: three days after creation or last use;
- local backups: only older, expired, restore-verified nodes outside the
  latest/rollback/protected chain;
- missing, malformed, or contradictory metadata: `legacy_unknown`, report only.

Names and directory age do not override missing evidence. The optional legacy
session fallback is allowed only for an explicitly supplied archive root whose
embedded `session_meta` is internally consistent and independently proven old.

## Reports

Each run, including dry-run, `NO_CHANGE`, `SKIPPED`, `PARTIAL`, and failure,
produces the following non-overwriting artifacts under the caller's
`report_dir`:

```text
disk-analysis-<run_id>.en.md
disk-analysis-<run_id>.zh-CN.md
disk-cleanup-<run_id>.en.md
disk-cleanup-<run_id>.zh-CN.md
disk-clean-report-<run_id>.html
```

The HTML report defaults to English and has an in-page Chinese toggle. It is
self-contained, uses no CDN or external font, supports manifest search/filter
and printing, and embeds the complete Markdown/JSON source so the visual layer
cannot replace or truncate audit evidence.

## Safety gates

The skill must stop with `SKIPPED` when identity, owner, target boundary,
metadata, active references, locks, platform quarantine, recovery evidence, or
the decisive report surface is unclear. It must not use global prune commands,
wildcard deletion, recursive deletion of an unresolved root, direct runtime
data-root deletion, or an estimated byte count as proof of reclaimed space.

`SUCCEEDED` requires same-target action-after readback. A quarantine still
occupies disk space; `reclaimed_bytes` is valid only after direct capacity
readback shows the space was actually returned to the volume.

## Optional post-deploy cleanup

Container image cleanup is an optional adapter. The release owner must provide
the project/runtime allowlist, exact revision and digest evidence, current and
rollback protection, an immutable recovery reference, and the release lock.
The adapter uses exact image IDs and official runtime APIs; it never substitutes
global image/system/volume prune or direct deletion under runtime data roots.

## Development and validation

From the skill directory:

```text
python -m py_compile scripts/render_report_html.py
python <skill-system-tools>/quick_validate.py .
python <skill-tools>/skill-eval-runner.py --root <skill-root> --target disk-clean audit
```

The HTML renderer is standard-library-only and refuses to overwrite an existing
report. Publishing, installing a helper, changing a runtime scope, or enabling
a new host is outside this package and requires a separate review and approval.
