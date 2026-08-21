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
