# Report contract

Every invocation must retain two non-overwriting Markdown reports and one non-overwriting HTML
page using the same UTC run_id, including dry-run, NO_CHANGE, SKIPPED, PARTIAL, and failed runs.
The caller supplies the output directory through report_dir or DISK_CLEAN_REPORT_DIR.

## Required files and timing

- disk-analysis-<run_id>.en.md: English inventory/classify/dry-run and pre-apply analysis. Write it
  successfully before any apply; if the write fails, do not apply and mark the run SKIPPED.
- disk-analysis-<run_id>.zh-CN.md: Chinese analysis for the same dataset.
- disk-cleanup-<run_id>.en.md: English post-apply action-after, cleanup action, rollback, and
  residual-risk report. Write it after action-after readback; a write failure is at least PARTIAL.
- disk-cleanup-<run_id>.zh-CN.md: Chinese cleanup report for the same dataset.
- disk-clean-report-<run_id>.html: self-contained Apple-style read/filter/print page that
  aggregates both Markdown reports, the complete manifest, every protection/skip reason,
  receipt, DecisionProof, and rollback information. For apply, generate it after action-after;
  for dry-run, SKIPPED, and NO_CHANGE, generate it after the final known state.

The page defaults to English and switches to Chinese. It must not depend on a CDN, external
fonts, or the network; it must preserve every manifest row and the complete source Markdown/JSON.
Use [scripts/render_report_html.py](../scripts/render_report_html.py) as the standard library
renderer. A rendering failure must be written to the cleanup receipt and makes the run at least
PARTIAL; never claim the web report is complete.

## Required content

Both Markdown reports must contain at least run_id, policy_version, host, target_key, observed_at,
proof_state, and evidence_refs. The analysis report must also contain total/used/free capacity,
logical size/file/directory/reparse counts for every allowed root, every candidate's absolute path,
category, state time, delete_after, size, owner, metadata, reference/lock checks, protected
objects, estimated_bytes, skipped items, and apply allowlist.

The cleanup report must also contain candidates, quarantined, deleted, skipped, failed,
estimated_bytes, quarantined_bytes, reclaimed_bytes, direct action-after readback, cleanup_status,
cleanup_receipt, rollback, residual_risk, proof state, empty_confirmation_status,
empty_started_at, pre_empty_quarantined_bytes, empty_action, empty_status,
post_empty_quarantined_bytes, and permanently_reclaimed_bytes.

For the initial post-quarantine report, set empty_confirmation_status to
awaiting_user_confirmation when the target Trash/Recycle Bin is non-empty, set empty_status to
pending, and set permanently_reclaimed_bytes to 0. Present the report before asking the user
whether to empty it. A confirmed empty phase is a new run_id with a fresh destructive proof and
its own action-after readback.

The HTML page is a presentation layer and must not change the cleanup conclusion. It must include
summary cards, capacity, categories, allowed roots, the complete candidate manifest, protected/
skipped objects, the evidence chain, rollback notes, quarantine/empty confirmation status,
pre/post empty sizes, and the complete source text of both Markdown reports plus receipt/proof.
Search and filtering may change visual display only; they must not remove or change underlying
records.

## Evidence and accounting

The report directory, report files, DecisionProof, and cleanup receipt are protected evidence,
not candidates. Exclude the report currently being generated and historical reports in that
directory from scanning. reclaimed_bytes and permanently_reclaimed_bytes may come only from
direct post-action capacity readback on the same volume. Logical size in the Windows Recycle Bin,
Linux desktop Trash, macOS Trash, or same-volume quarantine counts only as quarantined_bytes until
the user confirms the separate empty phase.

Report paths, DecisionProof, and cleanup receipt must cross-reference one another. If cleanup
report or HTML fails to write, do not mark the run SUCCEEDED; include reports, page, proof, and
paths in the cleanup receipt.
