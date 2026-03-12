# UNSER-inner

Operational workspace for UNSER.

## Directory layout

- `docs/company/`
  - Company profile, org, strategy, KPI definitions
- `docs/ops/`
  - Runbooks, SOPs, workflow notes
- `docs/meetings/`
  - Weekly and monthly meeting notes and agendas
- `data/office/`
  - Office-related raw exports and source files
- `data/posting/`
  - Posting-related raw exports and source files
- `data/sales/`
  - Sales data and pipeline exports
- `data/finance/`
  - Finance-related exports and supporting files
- `reports/`
  - Generated reports and summaries
- `scripts/`
  - Automation scripts and utilities
- `shared/`
  - Ad hoc files shared for agent review

## How to share files with the agent

1. Put files under one of the directories above.
2. Tell the agent the path you want reviewed.
3. For Google Sheets, share the URL and specify which sheet/tab matters.

## Notes

- Keep raw source data under `data/`.
- Keep human-readable references under `docs/`.
- Keep generated outputs under `reports/`.
- Keep repeatable automation under `scripts/`.
