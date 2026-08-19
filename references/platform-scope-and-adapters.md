# Platform scope and adapters

Prefer sidecar metadata next to the target object so metadata and object lifecycles remain
aligned. When a sidecar is unsuitable, use the caller-provided metadata_dir or
DISK_CLEAN_METADATA_DIR and record the absolute target path. These platform examples are
conventions, not auto-discovery or authorization to expand scope:

| Platform | Metadata directory | Main permitted object scope |
| --- | --- | --- |
| Windows | DISK_CLEAN_METADATA_DIR or caller-provided directory | TEMP and explicit application temporary/archive namespaces |
| Linux | DISK_CLEAN_METADATA_DIR or $XDG_STATE_HOME/disk-clean/metadata | TMPDIR and explicit application temporary/archive namespaces |
| macOS | DISK_CLEAN_METADATA_DIR or ~/Library/Application Support/disk-clean/metadata | TMPDIR and explicit application temporary/archive namespaces |

Never expand scope merely because a directory name contains temp, archive, backup, or session.

## Apply adapters

On Windows, Linux, and macOS, prefer the platform-native Trash/Recycle Bin. On headless systems
or without a native adapter, use same-volume quarantine with a manifest. Record quarantine as
quarantined_bytes until the user separately authorizes permanent emptying.

| Platform | Preferred isolation | Direct action-after evidence |
| --- | --- | --- |
| Windows | Native Recycle Bin or Shell API | source path gone, original-location match, isolation manifest readback |
| Linux | desktop Trash; same-volume quarantine when headless | source path gone, quarantine manifest, same-volume capacity readback |
| macOS | Native Trash or Finder API; same-volume quarantine without UI | source path gone, Trash/quarantine manifest, same-volume capacity readback |

Permanent deletion is allowed only when no platform adapter exists, the target fully satisfies
the policy, and the user explicitly authorizes it. Never run rm -rf or Remove-Item -Recurse over
an unexpanded or unchecked glob, root, or entire Temp. Never delete active sessions, backups,
databases, Docker volumes, VHDX, or unknown releases; never stop services or restart the host
or containers to release space; never expand to a sibling directory after a failed candidate.
If the adapter, isolation location, or recovery method is unclear, mark the candidate SKIPPED.
