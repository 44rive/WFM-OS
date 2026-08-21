# Power Query source

This directory is the reviewable source for every M query embedded in
`WFM_OS.xlsm`.

Query groups and load destinations are defined in
`00_Governance/00-01_ARCHITECTURE.md`. The executable installation order and
load destinations are declared in `MANIFEST.csv`.
Vendor-specific parsing is permitted only in staging adapters. Dimensions,
facts, outputs, and measures use canonical names exclusively.

For named schedules, Power Query also owns the approval-to-publication boundary.
`fact_PublishedRosterSegment` applies only the exact approved roster, swap,
leave, and publication versions. `stg_AuthoritativeScheduleIntervals` selects
either imported schedule intervals or that exact publication through one
non-overlapping `tblScheduleAuthority` row. It must never append both sources.

Every workbook release must record the Git commit from which its query source
was installed.
