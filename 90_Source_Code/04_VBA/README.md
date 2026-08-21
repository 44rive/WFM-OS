# VBA source

VBA is limited to controlled workbook actions that Excel formulas and refresh
settings cannot express cleanly, such as refresh sequencing, close-day snapshot
creation, backup, and publication.

Business metric logic does not belong in VBA. Every module embedded in the
workbook must also be exported here for review.

`modCloseDay.bas` is the reviewed source for the future `.xlsm` close-day
controller. It validates approval and Data Quality, consumes the reconciled
`tblCloseDayReady` output, and writes stable final rows to
`tblOperationalSnapshots`. It is intentionally not embedded in the committed
`.xlsx` shell.

`modPublishRoster.bas` is the reviewed source for controlled pseudonymous roster
export. It stamps one approved publication, refreshes and checks
`dq_RosterPublication`, validates exact version lineage, rejects identity
columns, writes UTF-8 CSV to a pre-existing restricted folder, and appends
`tblRosterPublicationLog`. The log remains `EXPORTED_HASH_REQUIRED` until an
external SHA-256 is recorded; export alone never makes the workbook operational.
