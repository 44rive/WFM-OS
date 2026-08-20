# Security and data handling

WFM OS processes workforce and operational data that may contain personal or
commercially sensitive information.

## Repository policy

- Only source code, documentation, blank templates, and anonymized fixtures may
  be committed.
- Real names, operational IDs, HR IDs, salaries, schedules, absences, contact
  records, and production exports are prohibited.
- Runtime data belongs under `data/`, which is ignored by Git.
- Generated operational packs belong under `outputs/`, also ignored by Git.
- Secrets and credentials must not be embedded in workbooks, M queries, VBA,
  Python, or configuration templates.

## Workbook policy

- The master workbook is an operational asset and should have a named owner.
- Distributed leadership outputs should exclude row-level PII unless explicitly
  required.
- Compensation data should use a separately restricted module or data source.
- Hidden worksheets are not an access-control mechanism.

Report accidental exposure to the repository owner immediately. Rotate exposed
credentials and remove sensitive Git history using an approved incident process.
