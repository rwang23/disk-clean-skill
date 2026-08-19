# 发布后保留期清理契约

本参考文件定义容器化发布成功后可选的清理边界。它与平台无关，并且以项目为范围。
发布流程负责部署；只有发布事务产生决定性证据后，disk-clean 才能检查并删除调用者
明确授权的精确产物。

## 门槛顺序

只有同一发布事务在匹配的主机和 runtime 上完成以下全部步骤后，finalizer 才有资格运行：

1. 源代码 revision 和所有生产镜像引用都精确且带 digest。
2. 已从线上项目读回 runtime 容器 image ID、revision 标签、迁移/就绪状态和服务健康状态。
3. 项目 owner 的外部 endpoint 或等价发布面读回目标 revision。
4. 事务已写入 committed receipt、JIT backup 证据和至少一个已验证的外部不可变恢复引用。

任一部署门槛失败，不能调用 finalizer。如果部署已验证但 finalizer 失败，部署仍保持
deployed，清理报告为 PARTIAL；不能静默回滚健康服务。

## 调用者提供的 allowlist

allowlist 是数据，不是发现机制。finalizer 必须为每个项目或 runtime 边界接收一条明确记录，
不在其中的对象一律拒绝：

| 字段 | 必须明确的边界 |
|---|---|
| project | 发布 owner 提供的稳定项目标识 |
| owner | 持有 release lock 的精确 owner 身份 |
| runtime | Docker、Podman 或其他经过审查的兼容 runtime |
| runtime_scope | 精确 daemon/socket/context 或等价 runtime 边界 |
| repository_allowlist | 精确镜像仓库或不可变产物命名空间 |
| release_evidence_ref | 包含 revision、readiness 和外部 readback 的 receipt |

未知项目、仓库、镜像前缀、runtime、socket 或路径都标记为 legacy_unknown，只报告不删除。

## 保护对象

inventory 前，finalizer 读取并记录：

- 每个生产服务当前的 container ID 和 image ID；
- 通过 readback 的目标 revision 和 digest；
- 事务 receipt/journal 中的 last-known-good 和活动 rollback image ID；
- 每个镜像的 registry 不可变 digest 或其他外部恢复引用；
- release 完成时间和共享 release lock 状态；
- volume、bind mount、数据库、release 目录和备份证据。

当前对象、last-known-good、被容器引用、被活动 rollback 事务持有，或缺少已验证外部
恢复引用的任何 image ID 都是 protected。即使名称看起来很旧，保护对象也不能进入 allowlist。

## 资格和动作

只有全部检查通过，产物才能进入 dry-run allowlist：

- 仓库/命名空间在调用者提供的 allowlist 中；
- 没有直接的 container 或 service 引用；
- 不是 current、last-known-good 或活动 rollback ID；
- digest 不可变并且可从外部恢复，或 release evidence 指向另一个已验证恢复来源；
- created_at/release_completed_at 满足类别 cutoff：无引用构建产物 3 天，previous/rollback
  发布产物 5 天；
- 同一 owner 能取得共享 release lock，且没有发布 worker 正在运行。

apply 只使用 dry-run 列出的精确 image ID 或 artifact ID，并调用 runtime 官方移除接口。
禁止全局 image/system/volume prune、通配符路径或直接删除 containerd、overlayfs、BuildKit
或 runtime data root 下的数据。被拒绝的产物记为 SKIPPED，不能因此扩大列表。

## Receipt 和 metadata

finalizer 在 release receipt 旁边或调用者提供的 metadata 目录下写入一条 owner-scoped
post_deploy_cleanup 记录。至少包括：

    run_id, release_id, project, owner, host, platform, runtime, policy_version
    release_completed_at, readback_ref, current_image_ids, protected_image_ids
    candidate_image_ids, deleted_image_ids, skipped_image_ids, failed_image_ids
    external_recovery_ref, estimated_bytes, quarantined_bytes, reclaimed_bytes
    cleanup_status, proof_state, evidence_refs, residual_risk

cleanup_status 只能是 SUCCEEDED、SKIPPED、PARTIAL 或 FAILED。
SUCCEEDED 必须有 action-after image inventory 和磁盘读回。SKIPPED 表示没有合格候选
或安全保护拒绝了本批次。PARTIAL 表示部署 readback 通过，但一个或多个清理动作或读回
失败。FAILED 只用于 finalizer 无法建立身份/before gate；它必须保持所有候选不变。

## Hook 边界和推广

hook 由已经持有精确 release lock 的 release gateway 或事务调用。CI 不得获得通用的特权
runtime socket，也不得用临时远程 shell 命令实现本策略。主机必须先安装经过审查的 helper，
并在 workflow 依赖 cleanup receipt 前读回其 allowlist/version。

安装 helper、改变 runtime 范围、添加仓库或启用新主机都是独立的 P3 操作：先 dry-run、
gateway/权限审查、受控 canary、直接 service/image/disk readback，然后再为其余 allowlist
目标启用。

