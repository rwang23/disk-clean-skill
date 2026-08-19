# Disk Clean

适用于 Windows、Linux 和 macOS 的便携式、证据优先磁盘清理 skill。

[英文](README.md)

> 免责声明：这是一个高权限清理 skill。它不会猜测路径，也不会仅按文件年龄删除对象。
> 每次运行都需要明确目标边界、dry-run、精确白名单和同一目标的 action-after 直接读回。
> 隔离区仍可能占用磁盘空间；本工具不是备份方案，也不是恢复方案。

## 安装

先克隆仓库，再把目录注册到你的 agent skill loader：

~~~bash
git clone https://github.com/rwang23/disk-clean-skill.git
~~~
安装后的目录名称应为 disk-clean，并且根目录必须包含 SKILL.md。如果你的 agent 支持
GitHub Skills，可以直接把这个仓库安装为 Skill。

## 直接交给 Agent 执行

把下面这段复制给 agent，并替换其中的占位符：

~~~text
请使用 disk-clean skill。我明确授权你只针对下面指定的平台和目标根执行清理流程。先做只读盘点和 dry-run，展示精确白名单、预计字节数、保护对象和跳过原因；只有我确认该白名单后才 apply。不要猜测路径，也不要处理活动任务、当前发布、数据库、备份、volume、虚拟磁盘、用户资料或未知对象。使用平台隔离/回收站适配器，完成同一目标的 action-after 直接读回，并生成英文和中文 Markdown 报告以及自包含 HTML 报告。平台：<windows|linux|macos>。目标根：<绝对路径列表>。报告目录：<绝对路径>。Metadata 目录：<绝对路径>。执行身份：<配置的 owner>。隔离方式：<native-trash|same-volume-quarantine>。
~~~

## 安全边界

Skill 可以分类失败构建、终态临时产物、过期归档 session、已验证旧备份、缓存和获准的
发布产物。活动任务、当前发布、恢复证据、数据库、volume、虚拟磁盘、用户资料和证据
不足的对象保持不动。永久删除不能替代备份或恢复测试。

## 报告预览

下面是截至“清理分类”部分的中文公开安全预览。候选路径、session 详情、备份详情和后续
证据部分涉及敏感信息，因此没有放入截图。

![中文报告预览](assets/report-overview-zh-CN.png)

## 校验

在 skill 目录执行：

~~~text
python -c "import ast, pathlib; ast.parse(pathlib.Path('scripts/render_report_html.py').read_text())"
~~~
