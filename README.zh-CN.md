# Disk Clean

适用于 Windows、Linux 和 macOS 的便携式、证据优先磁盘清理 skill。

[英文](README.md)

> 免责声明：这是一个高权限清理 skill。它不会猜测路径，也不会仅按文件年龄删除对象。
> 每次运行都需要明确目标边界、dry-run、精确白名单和同一目标的 action-after 直接读回。
> 隔离区仍可能占用磁盘空间；本工具不是备份方案，也不是恢复方案。Skill 不会自动清空
> 平台原生的暂存区：Windows 是调用者指定范围内的 **回收站（Recycle Bin）**，macOS 是
> 调用者指定范围内的 **废纸篓（Trash）**，Linux 是调用者指定范围内的桌面 **Trash**；
> 无桌面 Trash 适配器的 Linux 则使用精确的同卷 quarantine。Skill 会先呈现报告，再询问
> 用户是否进入单独的 destructive 清空阶段。

## 手动安装

先把仓库克隆到 agent 的 skill 目录，再将目录注册或重新加载到 agent 的 skill loader：

~~~bash
git clone https://github.com/rwang23/disk-clean-skill.git
~~~
安装后的 skill 名称应为 `disk-clean`，skill 根目录必须包含 `SKILL.md`。如果你的 agent
支持 GitHub Skills，也可以直接把这个仓库安装为 Skill。

## 让 Agent 安装

把下面这段复制给能够安装或注册 skill 的 agent：

~~~text
请从 https://github.com/rwang23/disk-clean-skill 安装 disk-clean skill 到你的 skill 目录。请用 disk-clean 这个名称注册或重新加载它，确认 skill 根目录包含 SKILL.md 和 agents/openai.yaml，并报告安装路径和校验结果。这里只做安装：不要扫描磁盘、执行清理、移动文件，也不要清空 Windows 回收站、macOS 废纸篓、Linux 桌面 Trash 或任何同卷 quarantine。
~~~

中文 Skill 说明仅供参考，不是运行入口：[references/SKILL.zh-CN.md](references/SKILL.zh-CN.md)。

## 让 Agent 执行

把下面这段复制给 agent，并替换其中的占位符：

~~~text
请使用 disk-clean skill。我明确授权你只针对下面指定的平台和目标根执行清理流程。先做只读盘点和 dry-run，展示精确白名单、预计字节数、保护对象和跳过原因；只有我确认该白名单后才 apply。不要猜测路径，也不要处理活动任务、当前发布、数据库、备份、volume、虚拟磁盘、用户资料或未知对象。使用平台对应的隔离适配器，完成同一目标的 action-after 直接读回，并生成英文和中文 Markdown 报告以及自包含 HTML 报告。先呈现报告并告诉我预计可清理大小，再询问我是否清空精确的平台暂存区：Windows 回收站、macOS 废纸篓、Linux 桌面 Trash，或无桌面 Linux 上指定的同卷 quarantine；不要自动清空。平台：<windows|linux|macos>。目标根：<绝对路径列表>。报告目录：<绝对路径>。Metadata 目录：<绝对路径>。执行身份：<配置的 owner>。隔离方式：<native-trash|same-volume-quarantine>。报告后清空：<ask-user|never>。
~~~

## 安全边界

Skill 可以分类失败构建、终态临时产物、过期归档 session、已验证旧备份、缓存和获准的
发布产物。活动任务、当前发布、恢复证据、数据库、volume、虚拟磁盘、用户资料和证据
不足的对象保持不动。永久删除不能替代备份或恢复测试。清空 Windows 回收站、macOS
废纸篓、Linux 桌面 Trash 或指定的同卷 quarantine，永远是报告之后、由用户确认的单独
destructive 阶段。

## 报告预览

下面是截至“清理分类”部分的中文公开安全预览。候选路径、session 详情、备份详情和后续
证据部分涉及敏感信息，因此没有放入截图。

![中文报告预览](assets/report-overview-zh-CN.png)

## 校验

在 skill 目录执行：

~~~text
python -c "import ast, pathlib; ast.parse(pathlib.Path('scripts/render_report_html.py').read_text())"
~~~
