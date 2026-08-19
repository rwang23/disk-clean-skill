# Disk Clean

Portable, evidence-first disk cleanup for Windows, Linux, and macOS.

[中文](README.zh-CN.md)

> Disclaimer: This is a high-permission cleanup skill. It does not guess paths or delete by
> age alone. It requires explicit target boundaries, a dry-run, an exact allowlist, and
> same-target action-after readback. Quarantine may still occupy disk space, and this tool is
> not a backup or recovery plan. The skill never empties a native Trash/Recycle Bin automatically:
> it presents the report first and asks the user before a separate destructive empty phase.

## Install

Clone the repository, then register the folder with your agent's skill loader:

~~~bash
git clone https://github.com/rwang23/disk-clean-skill.git
~~~
The folder must be installed as a skill named disk-clean and must contain the root file
SKILL.md. If your agent supports GitHub Skills, install this repository directly as a Skill.

## Run it with an agent

Copy this prompt to your agent and replace the placeholders:

~~~text
Use the disk-clean skill. I explicitly authorize the cleanup workflow for exactly the platform and target roots below. Start with read-only inventory and a dry-run, show the exact allowlist, estimated bytes, protected objects, and skip reasons, and apply only after I confirm that allowlist. Do not guess paths and do not touch active work, current releases, databases, backups, volumes, virtual disks, user profiles, or unknown objects. Use the platform quarantine/recycle adapter, perform same-target action-after readback, and generate the English and Chinese Markdown reports plus the self-contained HTML report. Present those reports before asking whether to permanently empty the specified Trash/Recycle Bin; do not empty it automatically. Platform: <windows|linux|macos>. Target roots: <absolute paths>. Report directory: <absolute path>. Metadata directory: <absolute path>. Actor: <configured owner>. Quarantine: <native-trash|same-volume-quarantine>. Empty after report: <ask-user|never>.
~~~

## Safety boundary

The skill may classify failed builds, terminal temporary artifacts, expired archived sessions,
verified old backups, caches, and approved release artifacts. It keeps active work, current
releases, recovery evidence, databases, volumes, virtual disks, user profiles, and uncertain
objects untouched. Permanent deletion is not a substitute for a backup or restore test. Emptying
Trash/Recycle Bin is always a separate user-confirmed destructive phase.

## Report preview

This public-safe preview shows the English report through the Classification section. Candidate
paths, session details, backup details, and later evidence sections are intentionally omitted.

![English report preview](assets/report-overview-en.png)

## Validation

From the skill directory:

~~~text
python -c "import ast, pathlib; ast.parse(pathlib.Path('scripts/render_report_html.py').read_text())"
~~~
