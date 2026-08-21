# Expected outputs

Approved expected results for anonymized fixtures belong here. They are stored
as readable CSVs so metric logic can be reviewed without executing a workbook.

The workforce-cycle outputs declare:

- effective-dated identity resolution, including an unknown identity;
- intraday staffing at 30-minute interval/activity grain;
- attendance at business-date/agent grain;
- conformance and adherence at interval/activity and business-date/agent grain;
- the exact unknown-identity quarantine record;
- the complete closed staffing state after an idempotent close day.

Rate fields use six decimal places. Count, second, and minute fields are exact
integers.

Planning outputs declare exact daily-to-interval reconciliation, complete
scenario totals, weekly PEAK paid-FTE requirements, recursive base supply, and
lead-time/seat-bounded hiring waves with their projected residual gaps.
