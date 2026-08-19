---
name: disk-clean
description: >
  按保留期限和机器边界安全执行磁盘清理。用户明确要求清理 Windows、Linux 或 macOS
  的临时/失败构建、已归档 session、测试产物、日志、缓存、备份或容器发布产物时使用；
  默认规则是失败构建不保留、previous/archive/历史发布保留 5 天、未引用镜像和
  BuildKit cache 保留 3 天。所有动作都要求先盘点、dry-run、决策证明、精确白名单和
  清理后读回；目标根、metadata、报告目录、执行身份和平台适配器必须由调用者明确提供。
  只做分析时使用 storage-analyzer，不使用本 skill。
---

> 这是仅供阅读的中文参考译文。Agent 的实际运行入口是仓库根目录的 `SKILL.md`；不要将本文件作为独立 Skill 加载。


将磁盘清理作为一次明确授权、可审计的 P3 操作执行。这个 skill 不创建常驻
runner，也不把删除动作交给 n8n；助手在用户明确说“清理”时按本规范运行，
构建和归档系统只负责写入 retention metadata。调用者必须传入平台、目标根、
报告目录、metadata 目录、执行身份和可用的隔离/回收适配器；skill 不从用户机器
猜测路径、用户名、主机名或项目名。详细 metadata 约定见
[metadata-contract.zh-CN.md](metadata-contract.zh-CN.md)；部署成功后的项目镜像
收敛契约见 [post-deploy-contract.zh-CN.md](post-deploy-contract.zh-CN.md)。

自动维护只做 owner-scoped、idle-only 的官方容器运行时操作和精确 job 工作区回收；
发布事务自己的 post-deploy finalizer 才能在同一项目、同一 release readback 成功后
处理过期且无引用的发布产物。它不改变本 skill 的 P3 授权边界。

## 与部署的隔离边界

正常 production release 的执行面始终由项目自己的 release workflow 和 runtime owner
负责；`disk-clean` 不启动、停止、注销、合并或改派 runner，也不把构建或部署切换到
另一种 hosted compute。发现 release workflow、worker、固定 gateway 事务或共享
release lock 正在使用时，清理批次必须 `SKIPPED`；只有同一 owner、runner 空闲、锁可
获得且对象仍在精确 allowlist 时，才可回收可再生对象。容器镜像还必须先完成同一发布
事务的 exact-revision、运行时和外部 readback；没有 readback 不能清理镜像。

## 发布后即时收敛

任何启用容器发布收敛的项目都必须把清理当作独立的 post-deploy finalizer：

1. 先完成 release revision、运行时 readiness 和外部 readback，并把成功 receipt
   与外部可恢复来源写入 release evidence；任一部署 gate 失败时不做镜像清理。
2. 在同一个项目 owner、同一个容器 runtime 和 release lock 上重新做 before 检查；读回
   当前容器 image ID、last-known-good、rollback/evidence 保护和候选镜像 digest。不能
   证明项目归属、外部恢复来源或无容器引用时记为 `SKIPPED`。
3. 只处理调用者提供的项目 allowlist 中 `post_deploy_project_image` 候选：previous/rollback 镜像
   从 `release_completed_at` 起超过 5 天，或明确无引用且 `created_at` 超过 3 天；当前
   image、last-known-good、活动 rollback、volume、container、数据库和 release 目录
   永不进入该批次。
4. 只调用匹配 runtime 的官方精确 image-ID 删除接口；禁止全局 image/system/volume prune
   以及手动删除 containerd/overlayfs/layer 数据。
5. 清理失败不回滚已经验证的服务，但部署回执必须是 `PARTIAL`，写出候选、实际删除、
   跳过原因和下一次可重试时间；只有 cleanup action-after readback 成功才记为 `SUCCEEDED`。

具体的 allowlist、保护对象、receipt 字段和 hook 安装边界见
[post-deploy-contract.md](post-deploy-contract.md)。

## 每次运行的报告契约

本版本的初始隔离报告如果 Trash/Recycle Bin 非空，必须记录
empty_confirmation_status=awaiting_user_confirmation、empty_status=pending 和
permanently_reclaimed_bytes=0；先呈现报告，再询问用户是否清空。用户明确同意后，清空
必须使用新的 run_id 和独立的 destructive proof。清理报告还应记录清空前后大小、empty
action、empty status、post-empty inventory 和永久释放空间。

每次调用本 skill 都必须生成一份硬盘分析报告和一份清理报告；包括 dry-run、
`NO_CHANGE`、`SKIPPED`、`PARTIAL` 和失败运行。报告使用 UTC `run_id` 命名，
不得覆盖旧报告。输出目录由调用者通过 `report_dir` 或
`DISK_CLEAN_REPORT_DIR` 提供；两份审计报告分别为：

- `disk-analysis-<run_id>.en.md`：inventory/classify 完成后、任何 apply 之前写入；
  写入失败时不得 apply，运行记为 `SKIPPED`。
- `disk-analysis-<run_id>.zh-CN.md`：与英文分析报告同一数据集的中文 companion。
- `disk-cleanup-<run_id>.en.md`：action-after 读回完成后写入；包含最终 proof、实际动作和
  residual risk。写入失败时不能记为 `SUCCEEDED`，至少记为 `PARTIAL`。
- `disk-cleanup-<run_id>.zh-CN.md`：与英文清理报告同一数据集的中文 companion。
- `disk-clean-report-<run_id>.html`：把本次分析报告、清理报告、完整候选 manifest、保护/跳过
  原因、evidence、rollback 和 receipt/proof 汇总成自包含的苹果风格网页；不得依赖 CDN、外部
字体或网络，必须保留所有 manifest 行和原始 Markdown/JSON 全文。apply 运行在 action-after
后生成，dry-run/`SKIPPED`/`NO_CHANGE` 运行在最终已知状态后生成；网页默认显示英文，可
切换中文；不得覆盖旧网页。

网页是审计 Markdown 的呈现层，不改变清理结论。标准库渲染器见
[../scripts/render_report_html.py](../scripts/render_report_html.py)；渲染失败必须写入 cleanup receipt，
运行至少记为 `PARTIAL`，不得伪装成网页报告已完成。

分析报告至少包含：`run_id`、policy version、host/identity、target scope、磁盘总量/已用/
可用、每个允许根的逻辑大小/文件数/目录数/reparse 数、metadata/owner/锁/进程引用、
候选的绝对路径/category/status 时间/`delete_after`/大小/证据、保护对象、dry-run 估算、
跳过原因和 DecisionProof 状态。清理报告至少包含：`candidates`、`quarantined`、`deleted`、
`skipped`、`failed`、`estimated_bytes`、`quarantined_bytes`、`reclaimed_bytes`、
action-after 直接读回、proof 状态、cleanup receipt、rollback 和 residual risk。

报告目录、报告文件和 DecisionProof/清理 receipt 是受保护的证据，不是清理候选；扫描时
必须排除正在生成的本次报告以及该报告目录内的历史报告。`reclaimed_bytes` 只能来自
清理后同一卷的直接容量读回；Windows Recycle Bin、Linux desktop Trash、macOS Trash 或
同卷 quarantine 中的逻辑大小只能记为 `quarantined_bytes`。

## 固定策略

使用 UTC 的状态时间，不用当前文件修改时间替代已知状态时间：

- `failed_build_temp`: 不保留；构建失败进入终态后立即清理可再生临时目录，metadata 的
  `delete_after` 等于 `terminal_at`。仍在运行、被进程引用或无法证明属于失败构建的对象不动。
- `security_scan_builder`: 不保留；安全扫描必须使用 job-scoped BuildKit builder，终态
  `finally`/`always()` 中删除 builder 和扫描镜像，失败也执行。
- `previous_release`, `archive_release`, `history_release`: 从 `archived_at`、
  `release_completed_at` 或严格命名中的 release 时间起保留 5 天。只有当前 release、
  当前运行镜像、最近一次已验证的外部恢复来源和活动事务受保护。
- `untagged_image`: 无容器引用、无 current/last-known-good 保护且 `created_at` 超过
  3 天后，才通过 Docker 官方 prune 接口回收。
- `rootless_helper_image`: 项目专属 rootless daemon 没有运行容器、镜像不是生产 current
  image 且超过 3 天时，可在该 owner socket 上用 `docker image prune --all` 回收可拉取的
  helper/tool image；rootful production daemon 不适用此自动规则。
- `buildkit_cache`: runner 空闲且 `last_used` 超过 3 天后，通过 rootless 对应 daemon
  的 `docker builder prune`/`docker buildx prune` 回收；禁止手动删除 BuildKit、containerd、
  overlayfs 或 rootless Docker 数据目录。
- `runner_job_workspace`: job 终态后不保留精确的 repository checkout/workspace；只允许
  回收明确的 `/srv/actions-runner/*/_work/<repo>` 路径，不包括 Runner 安装、`_tool`、
  unknown path 或 Docker 数据目录。
- `current_running_image`: 永不自动删除；必须先从同一运行时读回当前 digest/容器引用。
- `rollback_release`: 不无限保留；只有当前镜像和至少一个已验证的外部恢复来源存在时，
  才能删除本地未引用旧 rollback/release 对象。
- `post_deploy_project_image`: 仅由成功 release 的项目 finalizer 产生；必须绑定
  `release_id`/`release_completed_at`、exact-SHA readback、项目 allowlist、当前和
  last-known-good image ID、外部 immutable recovery reference。previous/rollback
  对象默认 5 天，普通无引用构建镜像默认 3 天；不接受全局 rootful prune。
- `local_backup`: disk-clean 不主动创建本地备份。部署所需的 JIT backup 仍由发布流程创建；
  清理时每个 owner/project 至少保留最新一份已通过 checksum、restore-list 和 offsite/
  immutable recovery 检查的备份，以及 backup chain 明确标记为 `protected` 的节点。较旧但
  已完成恢复检查、拥有合法 `delete_after`、不再是 latest/rollback 保护且已过期的备份，
  可以进入精确 allowlist；没有恢复检查、链角色不明或最新备份不完整时，整条备份链只报告不删。
- `temporary_artifact`: 由 metadata 标记为 terminal 的临时测试/工具输出，必须有 owner、
  `terminal_at`、`delete_after` 和 `retention_class=temporary_artifact`；过期、无任务/进程/
  研究证据引用后才可清理。缺少 metadata 时只能走下方 legacy fallback，不得因 `tmp`、
  `cache` 或目录年龄自动删除。
- `archived_session`: metadata 必须有 `state=archived`、与配置执行身份一致的 `owner`、`archived_at`、
  `session_id` 和 `delete_after=archived_at+14d`；只有 session 不在活动任务、无进程/锁、
  不在当前研究证据或恢复链中且 `delete_after <= now` 才能进入 allowlist。默认进入平台
  原生 Trash/Recycle Bin 或同卷 quarantine；缺 metadata、owner 不匹配或 session 身份不清楚
  时为 `legacy_unknown`，只报告。只有调用者明确提供的 session archive root 才可按下方
  `legacy_archived_session` fallback 处理可解析的嵌入式 `session_meta`。
- 数据库、Docker volume、虚拟磁盘和用户资料仍不按普通年龄规则删除。
- 缺少合法 metadata 的历史对象为 `legacy_unknown`。只有明确标记的失败构建或 terminal 临时对象在满足 legacy fallback 条件时，才可作为低置信度候选；历史 local backup、release 和 image 不自动删除。调用者明确提供的 archive root 中嵌入式 `session_meta` 只可按 `legacy_archived_session` fallback 处理。

当磁盘出现真实压力且普通 3 天 cutoff 不能解决可再生 BuildKit/构建缓存堆积时，只有在新鲜
P3 proof 证明对应 worker 空闲、没有运行容器、锁可用并得到用户明确授权后，才可以一次性
执行匹配 runtime 的官方全量 cache prune。它是人工恢复动作，不是按项目体积设 quota，也
不触及 volumes、current image、生产容器、数据库或 release 目录。

## 何时可以执行

1. 用户明确要求清理，并且目标机器/路径边界明确。
2. 先用只读扫描建立平台身份、磁盘 revision、候选列表和预计释放量。
3. 对每个独立平台/目标根分别建立 DecisionProof P3；不要把多个目标混成一个模糊目标。
4. 读取 [metadata-contract.md](metadata-contract.md)，确认候选的状态、时间、owner 和保护字段。
5. 先输出 dry-run，并在任何 apply 前把本次 `disk-analysis-<run_id>.en.md` 分析报告成功
   写入受保护的报告目录；只有白名单内、`delete_after <= now`、未被引用、未锁定、非当前
   镜像、且不是未完成恢复检查的备份，才可进入 apply。分析报告写入失败时不得 apply，
   运行记为 `SKIPPED`。

如果身份、owner、运行状态、回滚/备份边界或候选类别不清楚，停止该候选并报告
`SKIPPED`，不要扩大路径或改用全盘按年龄删除。

## 机器布局

metadata 优先使用目标对象旁边的 sidecar，避免 metadata 与对象生命周期脱节；
不能写 sidecar 时使用调用者提供的 `metadata_dir` 或 `DISK_CLEAN_METADATA_DIR`，并在
记录中保存绝对目标路径。以下是平台约定示例，不是自动发现或扩大范围的授权：

| 平台 | metadata 目录 | 允许的主要对象范围 |
|---|---|---|
| Windows | `%DISK_CLEAN_METADATA_DIR%` 或调用者提供的目录 | `%TEMP%`、明确的应用临时/归档命名空间 |
| Linux | `$DISK_CLEAN_METADATA_DIR` 或 `${XDG_STATE_HOME}/disk-clean/metadata` | `${TMPDIR}`、明确的应用临时/归档命名空间 |
| macOS | `$DISK_CLEAN_METADATA_DIR` 或 `$HOME/Library/Application Support/disk-clean/metadata` | `${TMPDIR}`、明确的应用临时/归档命名空间 |

不得因为目录名包含 `temp`、`archive`、`backup`、`session` 就自动扩大范围。

## 执行流程

### 1. Inventory

记录每台机器的 hostname、连接身份、磁盘容量/可用空间、目标路径、文件大小、
状态时间、metadata、owner、锁定/进程引用、当前 release 和服务状态。扫描过程中
只读，不先移动或删除。

### 2. Classify

按以下优先级分类：

1. `protected_active`: 正在运行、正在写入、被服务/进程引用、当前 release、当前研究任务。
2. `protected_backup`: 数据库备份、回滚 bundle、SQLite/WAL/SHM、Docker volume、VHDX。
3. `failed_build_temp`: 有 metadata 的失败构建，`delete_after <= now`；不保留。
4. `temporary_artifact`: terminal metadata 完整、`delete_after <= now` 且没有活动引用。
5. `archived_session`: 14 天规则满足、owner/身份/活动任务检查通过。
6. `previous_release`/`archive_release`: 5 天规则满足，且不是 current/last-known-good。
7. `security_scan_builder`/`runner_job_workspace`: job 已终态、owner 匹配、worker 空闲，
   只按 job/target 的精确 allowlist 回收。
8. `untagged_image`/`rootless_helper_image`/`buildkit_cache`: 3 天规则满足、无引用、worker
   空闲，使用匹配 runtime 的官方接口；production runtime 不执行全局 prune。
9. `post_deploy_project_image`: release readback 成功、项目归属和外部恢复来源可证明，
   只处理过期且无引用的 allowlist image ID。
10. `local_backup`: 只处理已验证恢复、明确过期且不受 latest/rollback/chain 保护的精确备份。
11. `legacy_archived_session`: 仅调用者明确提供的 archived-session 根目录中的嵌入式
    `session_meta`、14 天已过期、无活动/研究引用且两次 inventory 稳定；默认进入平台 Trash
    或同卷 quarantine。
12. `legacy_unknown`: 证据不足，报告但不动。

### 3. Dry-run

为每个候选输出：绝对路径、类别、状态时间、`delete_after`、大小、owner、证据、
保护检查结果、预估释放空间和跳过原因。不要用一个总数掩盖不同类别。

### 4. Before gate

每一批 apply 前重新读取相同目标的 identity/revision，并运行 DecisionProof `before`。
检查锁、进程、服务、当前 release、路径 realpath、符号链接/reparse point、权限和
目标仍在 allowlist。任何 drift 都新建 proof，不在旧 proof 上继续。

### 5. Apply

普通 apply 不清空 Trash/Recycle Bin。候选进入原生回收站或同卷 quarantine 后，先将
quarantined bytes 和预计大小写入报告；只有用户查看报告并明确同意，才进入独立的
destructive empty 阶段。

只对用户已授权且规则完整的候选执行精确清理。Windows、Linux 和 macOS 默认优先使用
平台原生 Trash/Recycle Bin；无桌面或无原生适配器时，使用同卷、带 manifest 的 quarantine。
结果记为 `quarantined`；隔离区仍占用原磁盘空间，只有用户另行明确授权永久清空后才把它
计入 `reclaimed_bytes`。只有在平台适配器不存在、目标完全符合规则且用户明确授权时，
才可精确永久删除，结果记为 `deleted`。禁止：

- `rm -rf`/`Remove-Item -Recurse` 作用于未展开核验的 glob、根目录或整棵 Temp；
- 删除 `sessions` 目录中的活动对象；
- 删除 backup、DB、Docker volume、VHDX 或未知 release；
- 为了释放空间停止服务、重启主机或重启容器；
- 因一个候选失败而扩大到同级目录。

平台适配器必须声明并验证：

| 平台 | 首选隔离方式 | action-after 直接证据 |
|---|---|---|
| Windows | Native Recycle Bin / Shell API | 源路径消失、原位置匹配、隔离 manifest 读回 |
| Linux | desktop Trash API；headless 使用同卷 quarantine | 源路径消失、quarantine manifest 和同卷容量读回 |
| macOS | Native Trash / Finder API；无 UI 时使用同卷 quarantine | 源路径消失、Trash/quarantine manifest 和同卷容量读回 |

若平台适配器、隔离位置或恢复方式不明确，候选必须 `SKIPPED`，不能降级成直接删除。

### 6. Verify, report and ask

在同一目标直接读回：候选路径是否消失、剩余候选数量/大小、磁盘可用空间、
服务/容器/release identity 是否未变。记录 `deleted`、`skipped`、`failed`、实际
释放量和 residual risk，写入 `disk-cleanup-<run_id>.en.md` 与中文 companion，再渲染
`disk-clean-report-<run_id>.html` 网页，最后用 DecisionProof `close`；没有 action-after
读回就不能声称完成。网页必须展示摘要卡、容量、分类、允许根、完整候选 manifest、保护/跳过
对象、证据链、回滚说明，并嵌入两份 Markdown 与 receipt/proof 的完整原文。清理报告或网页
写入失败时运行至少记为 `PARTIAL`，不得记为 `SUCCEEDED`；所有报告、网页、proof 和路径
必须写入 cleanup receipt。报告写出后，Agent 才能询问用户是否永久清空调用者指定的
Trash/Recycle Bin；用户拒绝或没有回答时保持 quarantine pending，不得清空。

### 7. Optional permanent emptying

只有用户在查看报告后明确同意，才可以用新的 run_id 和独立 P3 destructive proof
重新读取指定 Trash/Recycle Bin 的对象数量、目标卷和清空前大小，再调用平台原生 empty
适配器。必须直接读回清空后的 Trash/quarantine inventory、同卷容量和残余对象，并生成
新的不覆盖报告和 HTML。无法证明精确范围时记为 SKIPPED；禁止在 Trash/Recycle Bin
内部使用未核验的递归删除。

## Legacy fallback

仅对缺少 metadata 的失败构建或 terminal 临时目录开放 legacy fallback，且必须同时满足：

- 位于显式 allowlist；
- 名称明确包含 `failed`、`partial`、`probe`、`cleanup` 或 `test` 等失败/临时标记，或是
  明确的 `build` 失败日志（`*.err.log`、`*.error.log` 或名称含 `build-error`）；
- 最后写入时间早于 3 天；
- 连续两次 inventory 都存在且大小稳定；
- 没有进程、服务、release 或任务引用；
- 不含 backup、数据库、用户资料或当前测试证据；
- dry-run 中单独标记 `legacy_fallback`。

对于 `previous-*` release 目录，只有名称包含可解析的 UTC release 时间、目录不在当前
release path、没有进程/挂载/服务引用，并且连续两次 inventory 大小稳定时，才允许在
dry-run 中标为 `legacy_release_timestamp`；不能用普通 mtime 代替状态时间。历史
archive/session、local_backup、镜像和不明确的临时对象没有 metadata 时只报告，不自动删除。

### Archived session legacy fallback

只有调用者明确传入的 `session_archive_root` 可使用该 fallback。每个文件必须是 JSONL，
第一条记录 `type=session_meta`，`payload.id` 必须与文件名中的 session ID 一致，嵌入式
UTC `timestamp` 必须早于 14 天 cutoff；连续两次 inventory 大小稳定，文件可独占读取，且
session ID 不在活动任务、当前研究证据、恢复链或本次报告/proof 中。满足全部条件的对象才
可标为 `legacy_archived_session` 并进入平台隔离层；任何一项不满足就标为 `legacy_unknown`。
不得对其他 archive/session 目录套用这个 fallback，也不能用文件 mtime 替代嵌入式 timestamp。

## 构建和归档的写入要求

所有新构建和归档流程必须在状态转换时写 metadata。至少包括：

- `started_at`、`terminal_at`、`state`、`owner`、`run_id`；
- `image_id`/`image_ids`（如产生镜像）、`cache_key`、`target_path`；
- `delete_after`、`retention_class`、`protection_reason`。
- `temporary_artifact` 还必须写 `task_id`、`terminal_at`、owner 和不早于终态的
  `delete_after`；`archived_session` 还必须写 `state=archived`、`session_id`、
  `archived_at` 和 `delete_after=archived_at+14d`。
- post-deploy cleanup 还必须写 `release_id`、`release_completed_at`、`readback_ref`、
  `current_image_ids`、`protected_image_ids`、`external_recovery_ref`、`cleanup_status`。

状态转换：

- 构建开始：`running`；
- 构建成功：`succeeded`，按 release/evidence 规则处理；
- 构建失败：写入 `terminal_at` 和 `delete_after=terminal_at`，并在 `finally`/`always()` 清理临时目录；
- 安全扫描：写入唯一 `cache_key` 和 builder 记录，并在终态删除 job-scoped builder、扫描镜像
  和临时 workspace；
- previous/archive/history 完成：写入 `archived_at` 或 `release_completed_at` 和 `delete_after=+5d`；
- 未引用镜像或 BuildKit cache：写入 `created_at`/`last_used` 和 `delete_after=+3d`；
- release 成功后产生的项目镜像清理：写入 `retention_class=post_deploy_project_image`、
  `delete_after`、readback 和保护 image ID；清理 action-after 失败时保留 metadata，状态为
  `partial`，不得伪装成部署失败或删除成功；
- 本地备份：写入 checksum、restore-list 检查结果、offsite/immutable recovery reference、
  `backup_chain_role`、`protected` 和 `delete_after`；没有恢复证据或链角色不明不得自动删除；
- terminal 临时产物：写入 `retention_class=temporary_artifact`、任务引用和终态时间；
- archived session：写入 `state=archived`、owner、session 身份、`archived_at` 和 14 天
  `delete_after`，并在 session 仍被活动任务引用时保持 protected。

metadata 无效、时间倒退、目标路径变化、owner 不匹配或状态不一致时，清理只报告。

平台的 idle maintenance timer 可在同一 owner 的 worker 空闲、无运行容器且共享 release
lock 可用时，调用官方 72 小时 builder/cache prune，并删除调用者明确列出的 job workspace。
timer 不运行 production runtime 的全局 prune，不删除 volume，也不删除 runner 工具链或本体。

## 输出格式

每次运行必须保留两份不覆盖历史记录的 Markdown 报告和一份不覆盖历史记录的 HTML 网页，
且使用同一个 UTC `run_id`：

- `disk-analysis-<run_id>.en.md`：inventory/classify/dry-run 和 apply 前的英文分析报告；
- `disk-analysis-<run_id>.zh-CN.md`：同一数据集的中文分析报告。
- `disk-cleanup-<run_id>.en.md`：apply 后 action-after、清理动作、回滚和 residual risk 的英文报告；
- `disk-cleanup-<run_id>.zh-CN.md`：同一数据集的中文清理报告。
- `disk-clean-report-<run_id>.html`：苹果风格的自包含阅读/筛选/打印页面，汇总上述两份
  Markdown、完整 manifest、所有保护/跳过原因、receipt、DecisionProof 和回滚信息。

两份报告都至少包含 `run_id`、`policy_version`、`host`、`target_key`、`observed_at`、
`proof_state` 和 `evidence_refs`。分析报告还必须包含每个候选的绝对路径、类别、状态时间、
`delete_after`、大小、owner、metadata、引用/锁检查、保护对象、`estimated_bytes`、
`skipped` 和 apply 白名单；清理报告还必须包含 `candidates`、`quarantined`、`deleted`、
`skipped`、`failed`、`estimated_bytes`、`quarantined_bytes`、`reclaimed_bytes`、
action-after 直接读回、`cleanup_status`、`cleanup_receipt`、rollback 和 `residual_risk`。

报告路径、DecisionProof 和 cleanup receipt 必须互相引用；分析报告写入失败不得 apply，
清理报告或 HTML 网页写入失败不得记为 `SUCCEEDED`。HTML 不得截断候选表，也不得以摘要
替代原文；网页中的搜索/筛选只改变视觉显示，不改变或删除底层记录。

本 skill 的成功标准是“按规则安全完成并验证”，不是“尽可能多删”。空间压力大时
也必须先扩大可证明范围，不能降低保护边界。
