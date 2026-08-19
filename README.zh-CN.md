# Disk Clean

面向 Windows、Linux 和 macOS 的安全、证据优先的保留期清理 skill。

`disk-clean` 面向助手或自动化宿主，将用户明确授权的清理组织成一笔可审计的事务：
盘点、分类、dry-run、精确白名单、before gate、隔离/删除、action-after 直接读回，以及
双语报告。

English 说明见 [README.md](README.md)。

## 能做什么

- 只扫描调用者明确提供的目标根；不会通过猜目录名、用户名、主机名或项目名来发现用户
  私有目录。
- 处理失败构建、终态临时产物、归档 session、已验证旧备份、缓存、发布产物，以及可选的
  post-deploy 容器产物。
- 保留活动任务、当前发布、恢复证据、数据库、volume、虚拟磁盘、未知路径和 metadata
  链不完整的对象。
- 平台适配器可用时，优先进入原生 Trash/Recycle Bin 或同卷隔离区，再考虑永久删除。
- 单独报告已隔离字节数和永久回收字节数。

## 平台边界

每次运行至少需要调用者提供以下配置：

```yaml
platform: windows | linux | macos
target_roots:
  - <绝对路径根目录 1>
  - <绝对路径根目录 2>
report_dir: <绝对报告目录>
metadata_dir: <绝对 metadata 目录>
actor: <配置的执行身份>
quarantine: native-trash | same-volume-quarantine
```

本包不假设固定的 home 目录、盘符、临时目录、session archive、项目、云主机、容器 socket
或用户名。`%TEMP%`、`$TMPDIR`、`$XDG_CACHE_HOME` 等平台约定只有在调用者解析成明确的
allowlist 后才能使用。

## 保留规则

默认策略保持保守：

- 失败构建：写入终态 metadata，并使用 `delete_after=terminal_at`；
- 终态临时产物：必须有完整的 owner/task/terminal metadata，且 `delete_after` 已到期；
- 归档 session：必须是 `state=archived`、owner/session 身份匹配，并满足
  `delete_after=archived_at+14d`；
- previous/archive/history 发布产物：从记录的发布状态时间起保留 5 天；
- 无引用构建镜像和缓存：从创建时间或最近使用时间起保留 3 天；
- 本地备份：只处理已过期、已完成恢复验证、且不在 latest/rollback/protected 链中的旧节点；
- metadata 缺失、损坏或互相矛盾：标记为 `legacy_unknown`，只报告不动。

缺少证据时，名称和目录年龄不能成为删除依据。可选的 legacy session fallback 只能用于
调用者明确提供的 archive root，并且必须证明其中嵌入的 `session_meta` 内部一致且已经过期。

## 报告

每次运行，包括 dry-run、`NO_CHANGE`、`SKIPPED`、`PARTIAL` 和失败运行，都会在调用者的
`report_dir` 下生成以下不覆盖历史的文件：

```text
disk-analysis-<run_id>.en.md
disk-analysis-<run_id>.zh-CN.md
disk-cleanup-<run_id>.en.md
disk-cleanup-<run_id>.zh-CN.md
disk-clean-report-<run_id>.html
```

HTML 网页默认显示英文，并提供页面内中文切换。网页自包含，不依赖 CDN 或外部字体，支持
manifest 搜索/筛选和打印，并嵌入完整 Markdown/JSON 原文，确保视觉层不会替代或截断审计证据。

## 安全门槛

当身份、owner、目标边界、metadata、活动引用、锁、平台隔离层、恢复证据或决定性报告面
不清楚时，必须以 `SKIPPED` 停止。禁止全局 prune、通配符删除、未经展开核验的根目录递归
删除、直接删除 runtime data root，或把预计字节数当作实际释放空间的证明。

`SUCCEEDED` 必须有同一目标的 action-after 直接读回。隔离区仍占用磁盘空间；只有同卷容量
直接读回确认空间已返回后，才能计入 `reclaimed_bytes`。

## 可选的 post-deploy 清理

容器镜像清理是可选适配器。发布 owner 必须提供项目/runtime allowlist、精确 revision 和
digest 证据、current/rollback 保护、不可变恢复来源及 release lock。适配器只使用精确 image
ID 和 runtime 官方 API，不替换为全局 image/system/volume prune，也不直接删除 runtime data root。

## 开发和验证

在 skill 目录执行：

```text
python -m py_compile scripts/render_report_html.py
python <skill-system-tools>/quick_validate.py .
python <skill-tools>/skill-eval-runner.py --root <skill-root> --target disk-clean audit
```

HTML 渲染器只使用 Python 标准库，并拒绝覆盖已经存在的报告。发布、安装 helper、改变 runtime
范围或启用新主机不属于本包，需要单独审查和授权。
