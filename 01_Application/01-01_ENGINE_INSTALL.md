# 01-01 · Engine installation and release gate

`WFM_OS.xlsx` is currently the reproducible, data-free application shell. It is
not operational until genuine Excel engines are installed and validated in
Microsoft 365 desktop Excel.

## Implemented source slices

The first operational slice is:

```text
generic contact CSV
  -> configurable source/field/value mappings
  -> canonical contact staging
  -> dated queue/activity mapping
  -> live and closed contact facts
  -> Power Pivot relationships
  -> explicit DAX service measures
  -> Data Quality and reconciliation outputs
```

No source name or business page depends on a contact-platform vendor.

The second source slice is:

```text
effective-dated people and source identities
  + generic schedule, login, state-event, and requirement CSVs
  -> 30-minute schedule-led operational intervals
  -> live and closed operational/requirement facts
  -> interval staffing, attendance, adherence, and exception outputs
  -> explicit operational DAX measures
  -> approved close-day candidate and controlled snapshot publisher
```

The planning foundation is:

```text
closed interval demand
  -> governed forecast history
  -> deterministic Python daily baseline and approved adjustments
  -> reviewed interval forecast versions
  -> forecast accuracy facts and DAX
  -> Erlang C or workload capacity candidates
  -> reviewed requirement approvals
  -> shared closed/live staffing-requirement facts
```

Daily forecast output is deliberately not treated as interval demand. A
reviewed intraday profile must reconcile daily totals into interval rows before
capacity is run.

## Install Power Query

Run the preflight and prepared-copy installer described in
`01_Application/01-02_DESKTOP_RELEASE_CHECKLIST.md` before applying load
destinations. The installer adds reviewed M definitions but deliberately leaves
loads and refresh validation as manual release gates.

1. Open the generated workbook in Microsoft 365 desktop Excel.
2. Confirm that `59_PARAMETERS` through `73_CAPACITY_POLICIES` contain the expected
   named tables.
3. Set an absolute `RootPath`, deployment profile, and `AsOfDate`.
4. Install the queries in
   `90_Source_Code/01_Power_Query/MANIFEST.csv` order.
5. Apply the exact load destination in the manifest.
6. Enable the configured contact source only after its mappings are complete.
7. For operational control, enable exactly one scheduling, login, agent-event,
   and staffing-requirement source only after identity, activity, schedule-type,
   and state mappings are complete.

Power Query source is canonical in Git. Do not paste source into a visible
business sheet.

## Create Power Pivot relationships

`90_Source_Code/02_DAX/RELATIONSHIPS.csv` is the machine-readable source of
truth for relationship order, columns, cardinality, direction, active state,
and requirement. Its current contract is:

```text
fact_ContactClosed[BusinessDate] -> dim_Date[Date]
fact_ContactLive[BusinessDate]   -> dim_Date[Date]
fact_ContactClosed[IntervalKey]  -> dim_Interval[IntervalKey]
fact_ContactLive[IntervalKey]    -> dim_Interval[IntervalKey]
fact_ContactClosed[ActivityKey]  -> dim_Activity[ActivityKey]
fact_ContactLive[ActivityKey]    -> dim_Activity[ActivityKey]
fact_ContactClosed[QueueKey]     -> dim_Queue[QueueKey]
fact_ContactLive[QueueKey]       -> dim_Queue[QueueKey]
fact_ContactClosed[ChannelKey]   -> dim_Channel[ChannelKey]
fact_ContactLive[ChannelKey]     -> dim_Channel[ChannelKey]
fact_OperationalIntervalClosed[BusinessDate] -> dim_Date[Date]
fact_OperationalIntervalLive[BusinessDate]   -> dim_Date[Date]
fact_OperationalIntervalClosed[IntervalKey]  -> dim_Interval[IntervalKey]
fact_OperationalIntervalLive[IntervalKey]    -> dim_Interval[IntervalKey]
fact_OperationalIntervalClosed[ActivityKey]  -> dim_Activity[ActivityKey]
fact_OperationalIntervalLive[ActivityKey]    -> dim_Activity[ActivityKey]
fact_OperationalIntervalClosed[AgentKey]     -> dim_Agent[AgentKey]
fact_OperationalIntervalLive[AgentKey]       -> dim_Agent[AgentKey]
fact_StaffingRequirementClosed[BusinessDate] -> dim_Date[Date]
fact_StaffingRequirementLive[BusinessDate]   -> dim_Date[Date]
fact_StaffingRequirementClosed[IntervalKey]  -> dim_Interval[IntervalKey]
fact_StaffingRequirementLive[IntervalKey]    -> dim_Interval[IntervalKey]
fact_StaffingRequirementClosed[ActivityKey]  -> dim_Activity[ActivityKey]
fact_StaffingRequirementLive[ActivityKey]    -> dim_Activity[ActivityKey]
fact_Forecast[BusinessDate]      -> dim_Date[Date]
fact_Forecast[IntervalKey]       -> dim_Interval[IntervalKey]
fact_Forecast[ActivityKey]       -> dim_Activity[ActivityKey]
fact_Forecast[ChannelKey]        -> dim_Channel[ChannelKey]
fact_ForecastAccuracy[BusinessDate] -> dim_Date[Date]
fact_ForecastAccuracy[IntervalKey]   -> dim_Interval[IntervalKey]
fact_ForecastAccuracy[ActivityKey]   -> dim_Activity[ActivityKey]
fact_ForecastAccuracy[ChannelKey]    -> dim_Channel[ChannelKey]
```

Mark `dim_Date` as the Date Table using its `Date` column. Do not create a
relationship between the live and closed facts.

## Install measures

Install `90_Source_Code/02_DAX/service.dax` and
`90_Source_Code/02_DAX/operational_control.dax` and
`90_Source_Code/02_DAX/planning.dax` as explicit measures. Business
pages must consume these measures rather than recreate them with worksheet
formulas. Use `90_Source_Code/02_DAX/MANIFEST.csv` for home tables, formats,
display folders, and descriptions. Measures labelled `· Interval` require
interval-grain filter context.

## Install Python in Excel

Follow `01_Application/01-03_PYTHON_INSTALL.md` and
`90_Source_Code/03_Python/MANIFEST.csv`. Install the three definition cells and
two entrypoint cells in exact order. Forecast and capacity outputs remain
candidates until they are reviewed and pasted into `tblForecastVersions` and
`tblRequirementApprovals` with complete approval evidence.

## Install close day

1. Load `out_CloseDaySnapshot` into `95_QUERY_OUTPUTS!tblCloseDayReady`.
2. Save an installation copy as `.xlsm`.
3. Import `90_Source_Code/04_VBA/modCloseDay.bas`.
4. Assign `CloseOperationalDay` to a controlled button on `84_CLOSE_DAY`.
5. Keep `94_SNAPSHOT_STORE` hidden from normal operation, but do not present
   worksheet hiding as a security control.

The controller refuses an unapproved request, incomplete Data Quality state,
missing requirement, duplicate key, or partial existing final snapshot. The
committed `.xlsx` shell does not contain or claim this macro.

## Validate

Use `91_Tests/anonymized-input/contacts_valid.csv` and compare daily results to
`91_Tests/expected-output/contact_daily_metrics.csv`.

For operational control, run every fixture in
`91_Tests/anonymized-input/` and reconcile interval staffing, daily attendance,
interval/daily adherence, identity quarantine, and close-day output to the
matching files under `91_Tests/expected-output/`.

The release remains blocked until:

- both refresh lanes execute;
- lookup keys are unique;
- live and closed dates do not overlap;
- the contact reconciliation output passes;
- the golden fixture metrics match;
- unknown queue fixture rows appear in Data Quality rather than disappearing;
- source-system-scoped identities resolve at the event date;
- schedule, login, and state overlaps are zero or explicitly blocking;
- interval staffing, attendance, conformance, and adherence match the golden
  fixtures;
- planning baseline, adjustment, accuracy, and capacity results match the
  planning fixtures;
- forecast candidates cannot bypass `tblForecastVersions`, and requirements
  cannot bypass `tblRequirementApprovals`;
- daily forecast totals reconcile exactly to the reviewed interval profile;
- the close-day controller is idempotent and creates no duplicate final keys;
- a second refresh produces identical finalized results;
- the workbook passes visual inspection in desktop Excel.

Only after these checks should `BUILD_INFO` be updated and the file promoted to
the first operational release.
