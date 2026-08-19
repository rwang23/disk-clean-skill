# Retention Metadata Contract

## Schema

每个构建、发布副本、未引用镜像、BuildKit cache 或 archived session 关联一个 JSON
metadata 对象。时间统一使用带 `Z` 的 ISO-8601 UTC；字段不得包含 token、cookie、客户
内容或完整 session 内容。

```json
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
```

成功发布使用同一 schema，但 `state=succeeded`、`retention_class=release_image`。当前
运行镜像或已验证的外部恢复来源保护对象的 `delete_after` 可以为 `null`；一旦不再是
current/last-known-good，发布流程必须补写 `release_completed_at`、保护解除证据和
`delete_after=release_completed_at+5d`。

未引用镜像和 BuildKit cache 使用 `retention_class=untagged_image` 或 `buildkit_cache`，
以 `created_at`/`last_used` 加 3 天计算 `delete_after`。

成功 release 的项目镜像收敛使用 `retention_class=post_deploy_project_image`。这不是
“部署成功即可删除”的别名；记录必须绑定 `release_id`、`release_completed_at`、同一
目标的 exact-SHA/readiness/public `readback_ref`、当前和受保护 image ID，以及已验证的
外部 immutable recovery reference。previous/rollback 对象按 release 完成时间保留 5 天；
普通无引用构建镜像按创建时间保留 3 天。清理记录的 `cleanup_status` 必须是
`SUCCEEDED`、`SKIPPED`、`PARTIAL` 或 `FAILED`。

本地数据库备份使用 `retention_class=local_backup`，必须额外记录：

```json
{
  "checksum": "sha256:...",
  "checksum_verified_at": "2026-08-03T23:15:00Z",
  "restore_list_verified_at": "2026-08-03T23:16:00Z",
  "offsite_reference": "masked-or-null",
  "delete_after": "2026-08-10T23:15:00Z"
}
```

Archived session 继续使用：

```json
{
  "schema_version": 2,
  "kind": "archived_session",
  "state": "archived",
  "owner": "configured-owner",
  "target_path": "${SESSION_ARCHIVE_ROOT}/example.jsonl",
  "session_id": "masked-session-id",
  "archived_at": "2026-08-03T23:12:00Z",
  "retention_days": 14,
  "delete_after": "2026-08-17T23:12:00Z",
  "source": "session-archive"
}
```

Terminal 临时测试/工具产物使用 `retention_class=temporary_artifact`，至少记录
`task_id`、`terminal_at`、`owner`、`delete_after` 和 `protection_reason`。只有任务已经
终态、无活动进程/锁/研究证据引用且 `delete_after` 已到期，才可以进入 disk-clean 的
精确 allowlist；不能用 `tmp`、`cache` 或目录年龄代替 metadata。

## Invariants

- 每次 build 必须有 `started_at`、`terminal_at`、`state`、`image_id`/`image_ids`、
  `cache_key` 和 `delete_after` 字段；字段没有值时必须显式为 `null`，不能省略。
- `retention_class=failed_build_temp` 必须有 `state=failed`、`terminal_at` 和
  `delete_after=terminal_at`。
- 失败 build 必须在 `finally`/`always()` 写终态 metadata 并清理可再生临时目录。
- `retention_class=temporary_artifact` 必须有 terminal `state`、`task_id`、`terminal_at`、
  `owner` 和 `delete_after`；`delete_after` 不得早于 `terminal_at`，活动任务或研究证据
  引用存在时必须保持 protected。
- `retention_class=archived_session` 必须有 `state=archived`、与配置执行身份一致的 `owner`、`session_id`、
  `archived_at` 和 `delete_after=archived_at+14d`；活动任务、进程、锁、当前研究证据或
  恢复链引用存在时不得进入 allowlist。
- `retention_class=local_backup` 必须有 checksum、checksum/restore-list 验证时间、
  `backup_chain_role`、`protected` 和 offsite/immutable recovery reference；latest、
  rollback 或 chain-protected 节点不得删除，旧节点只有在恢复验证完成且 `delete_after`
  到期后才可进入精确 allowlist。
- `previous_release`/`archive_release`/`history_release` 的 `delete_after` 必须等于
  完成时间加 5 天。
- `untagged_image`/`buildkit_cache` 的 `delete_after` 必须等于创建或最后使用时间加 3 天。
- `post_deploy_project_image` 必须有 release/readback/保护/恢复字段；没有这些证据时
  必须分类为 `legacy_unknown` 或 `SKIPPED`，不得由名称或空间压力推断可删。
- `cleanup_status=SUCCEEDED` 必须有候选 action-after image inventory 和磁盘读回；
  部署已经成功但清理动作或读回失败时必须记为 `PARTIAL`，不能伪装为 `FAILED` deploy。
- `delete_after` 必须等于对应状态时间加上策略天数；失败 build 的策略天数为 0。调用者
  不能任意缩短。
- `target_path` 必须是绝对路径，并与实际 sidecar 所属对象一致。
- metadata 缺失、JSON 损坏、路径不一致、owner 不一致、字段缺失或时钟倒退时，分类为
  `legacy_unknown`，不可自动删除；严格命名的 `previous-*` 只能使用 skill 中的
  `legacy_release_timestamp` fallback。
- 缺失或不完整的 archived-session、local-backup 或 temporary-artifact metadata 不得
  通过名称、目录年龄或空间压力升级为可删除对象。
- 调用者明确提供的 `session_archive_root` 是唯一允许的 legacy session fallback 根目录；
  仅当 JSONL 首条 `session_meta` 的 `payload.id` 与文件名一致、嵌入式 UTC `timestamp` 已
  超过 14 天且没有活动/研究/恢复引用时，才可分类为 `legacy_archived_session` 并进入
  平台隔离层。其他缺 metadata 的 session 仍为 `legacy_unknown`。
- 成功构建不能伪装为失败构建；发布、测试证据、回滚副本使用单独类别。

## Placement

优先使用：

```text
<artifact-directory>/.retention.json
```

如果目录不适合放 sidecar，则使用机器专属或 owner 专属目录：

```text
Windows: %DISK_CLEAN_METADATA_DIR%\<run-id>.json
Linux:   $DISK_CLEAN_METADATA_DIR/<run-id>.json
macOS:   $DISK_CLEAN_METADATA_DIR/<run-id>.json
```

集中 metadata 记录仍然必须保存 `target_path`、owner 和对象 fingerprint；对象移动、
重命名或发布完成后，应先更新 metadata，再允许清理流程看到它。

## State transitions

```text
build: running -> succeeded
build: running -> failed -> cleaned
release: current -> previous -> eligible_after_5d -> deleted
image/cache: created -> unreferenced -> eligible_after_3d -> pruned
release image: current -> previous/rollback -> eligible_after_5d -> post_deploy_cleanup -> pruned
temporary artifact: running -> terminal -> eligible_after_delete_after -> quarantined/deleted
session: active -> archived -> eligible_after_14d -> deleted
local backup: created -> checksum/restore_verified -> expired -> eligible_after_delete_after -> deleted
```

失败构建的可再生临时目录由构建流程的 `finally`/`always()` 立即清理；disk-clean
负责遗留失败对象和 metadata 记录。其他历史对象只能由 disk-clean 的一次 apply 运行
写入删除/回收结果；构建或归档流程不得自行删除历史对象并声称已完成 retention。

