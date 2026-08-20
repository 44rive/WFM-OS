# 01-01 · Engine installation and release gate

`WFM_OS.xlsx` is currently the reproducible, data-free application shell. It is
not operational until genuine Excel engines are installed and validated in
Microsoft 365 desktop Excel.

## First vertical slice

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

## Install Power Query

1. Open the generated workbook in Microsoft 365 desktop Excel.
2. Confirm that `59_PARAMETERS` through `69_METRIC_RULES` contain the expected
   named tables.
3. Set an absolute `RootPath`, deployment profile, and `AsOfDate`.
4. Install the queries in
   `90_Source_Code/01_Power_Query/MANIFEST.csv` order.
5. Apply the exact load destination in the manifest.
6. Enable the configured contact source only after its mappings are complete.

Power Query source is canonical in Git. Do not paste source into a visible
business sheet.

## Create Power Pivot relationships

Create single-direction one-to-many relationships:

```text
fact_ContactClosed[BusinessDate] -> dim_Date[Date]
fact_ContactLive[BusinessDate]   -> dim_Date[Date]
fact_ContactClosed[IntervalKey]  -> dim_Interval[IntervalKey]
fact_ContactLive[IntervalKey]    -> dim_Interval[IntervalKey]
fact_ContactClosed[ActivityKey]  -> dim_Activity[ActivityKey]
fact_ContactLive[ActivityKey]    -> dim_Activity[ActivityKey]
fact_ContactClosed[QueueKey]     -> dim_Queue[QueueKey]
fact_ContactLive[QueueKey]       -> dim_Queue[QueueKey]
```

Mark `dim_Date` as the Date Table using its `Date` column. Do not create a
relationship between the live and closed facts.

## Install measures

Install `90_Source_Code/02_DAX/service.dax` as explicit measures. Business pages
must consume these measures rather than recreate them with worksheet formulas.

## Validate

Use `91_Tests/anonymized-input/contacts_valid.csv` and compare daily results to
`91_Tests/expected-output/contact_daily_metrics.csv`.

The release remains blocked until:

- both refresh lanes execute;
- lookup keys are unique;
- live and closed dates do not overlap;
- the contact reconciliation output passes;
- the golden fixture metrics match;
- unknown queue fixture rows appear in Data Quality rather than disappearing;
- a second refresh produces identical finalized results;
- the workbook passes visual inspection in desktop Excel.

Only after these checks should `BUILD_INFO` be updated and the file promoted to
the first operational release.
