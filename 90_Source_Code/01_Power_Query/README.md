# Power Query source

This directory is the reviewable source for every M query embedded in
`WFM_OS.xlsm`.

Query groups and load destinations are defined in
`00_Governance/00-01_ARCHITECTURE.md`.
Vendor-specific parsing is permitted only in staging adapters. Dimensions,
facts, outputs, and measures use canonical names exclusively.

Every workbook release must record the Git commit from which its query source
was installed.
