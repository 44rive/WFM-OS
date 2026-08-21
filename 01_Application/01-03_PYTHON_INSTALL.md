# Python in Excel installation

This is a controlled desktop-release step. The committed `.xlsx` shell does
not contain Python cells and remains `NOT OPERATIONAL` until the complete
release checklist passes.

Python in Excel runs in Microsoft's cloud container. It cannot read the local
repository or make network requests. Power Query must first load the governed
tables into the workbook, and the Python source must then be installed as
static `=PY(...)` cells in the order declared by
`90_Source_Code/03_Python/MANIFEST.csv`.

## Preconditions

1. Use a supported Microsoft 365 desktop build with Python in Excel enabled.
2. Install every Power Query definition and its declared load destination.
3. Refresh successfully with a configured, nonblank deployment profile.
4. Confirm `dq_PlanningApprovals` contains no blocking rows.
5. Keep the workbook calculation mode automatic and use the manifest's
   row-major cell order.

Microsoft references:

- <https://support.microsoft.com/en-us/excel/python/data-security-and-python-in-excel>
- <https://support.microsoft.com/en-us/excel/python/use-power-query-to-import-data-for-python-in-excel>
- <https://support.microsoft.com/en-gb/office/get-started-with-python-in-excel-a33fbcbe-065b-41d3-82cf-23d05397f53d>
- <https://support.microsoft.com/en-us/excel/python/py-function>

## Install definitions

For each `DEFINITIONS` row in the Python manifest, open the declared source
file, copy its complete text, and create a Python cell at the declared sheet
and anchor. Do not translate, abbreviate, or merge the source files. Calculate
each cell successfully before installing the next one.

The source order is deliberate:

1. `forecast.py` — baseline, backtest, and governed adjustment rules.
2. `capacity.py` — Erlang C and workload capacity rules.
3. `planning.py` — intraday allocation, complete scenarios, and weekly PEAK
   requirement aggregation.
4. `supply.py` — recursive paid supply and deterministic hiring waves.
5. `excel_adapter.py` — DataFrame-to-record boundary only.

## Install forecast entrypoint

At `92_PY_FORECAST!B15`, install this Python cell and return an Excel value:

```python
parameters = xl("tblParameters[#All]", headers=True)
forecast_candidates = run_forecast_excel(
    xl("out_ForecastHistory[#All]", headers=True),
    xl("tblForecastPolicies[#All]", headers=True),
    xl("tblCalendarEvents[#All]", headers=True),
    xl("tblForecastOverrides[#All]", headers=True),
    profile=str(parameter_value_excel(parameters, "EnterpriseProfile")),
    as_of_date=parameter_value_excel(parameters, "AsOfDate"),
)
pd.DataFrame(forecast_candidates)
```

The output is a daily analytical candidate. It is not an approved forecast.
Approved rows in `tblForecastOverrides` also operate at daily `ForecastDate`
grain; one absolute override per activity, channel, and date has precedence over
calendar percentages.

## Install interval and scenario entrypoint

At `93A_PY_INTERVAL!B15`, install this Python cell and return an Excel value:

```python
parameters = xl("tblParameters[#All]", headers=True)
interval_candidates = run_intraday_excel(
    pd.DataFrame(forecast_candidates),
    xl("tblIntradayProfiles[#All]", headers=True),
    xl("tblScenarioInputs[#All]", headers=True),
    profile=str(parameter_value_excel(parameters, "EnterpriseProfile")),
)
pd.DataFrame(interval_candidates)
```

Review the complete BASE and approved scenario horizons. Prove that every daily
volume reconciles exactly to its 48 interval rows, document the source run, and
paste only reviewed rows into `tblForecastVersions` on
`85_FORECAST_APPROVAL`. Create stable row/version keys and complete every
approval field. Python cannot write to or approve that table.

## Install capacity entrypoint

After approved interval forecasts refresh into `out_ApprovedForecast`, install
this Python cell at `93B_PY_CAPACITY!B15` and return an Excel value:

```python
parameters = xl("tblParameters[#All]", headers=True)
capacity_candidates = run_capacity_excel(
    xl("out_ApprovedForecast[#All]", headers=True),
    xl("tblCapacityPolicies[#All]", headers=True),
    xl("tblScenarioInputs[#All]", headers=True),
    profile=str(parameter_value_excel(parameters, "EnterpriseProfile")),
)
pd.DataFrame(capacity_candidates)
```

Review and reconcile these candidates, then paste the approved interval rows
into `tblRequirementApprovals` on `86_REQUIREMENT_APPROVAL`. Only valid approved
rows enter the canonical staffing-requirement facts.

## Install supply and hiring entrypoints

After approved requirements refresh, install this Python cell at
`93C_PY_SUPPLY!B15` and return an Excel value:

```python
parameters = xl("tblParameters[#All]", headers=True)
supply_candidates, hiring_candidates = run_supply_excel(
    xl("out_ApprovedRequirementPlan[#All]", headers=True),
    xl("out_WorkforceSupplySnapshot[#All]", headers=True),
    xl("tblSupplyAssumptions[#All]", headers=True),
    xl("tblHiringPolicies[#All]", headers=True),
    profile=str(parameter_value_excel(parameters, "EnterpriseProfile")),
    as_of_date=parameter_value_excel(parameters, "AsOfDate"),
)
pd.DataFrame(supply_candidates)
```

At `93D_PY_HIRING!B15`, expose the hiring half of the same deterministic run:

```python
pd.DataFrame(hiring_candidates)
```

Review lead dates, timing status, yield, seat splitting, and proficiency. Paste
the hiring rows into `tblHiringPlanVersions` with one plan version and complete
approval evidence. Refresh and clear `dq_PlanningApprovals`, then paste the
matching supply rows into `tblSupplyPlanVersions`. Hiring must be approved
first: supply approval is blocked unless cumulative proficient approved hiring
FTE equals `PlannedHirePaidFTE` at each plan/scenario/activity/period grain.

## Release evidence

Record screenshots or exported evidence showing:

- all ten manifest cells calculate without errors;
- all candidate DataFrames have stable headers and nonnegative values;
- future history beyond `p_AsOfDate` does not affect the forecast;
- a draft forecast cannot become a canonical fact;
- each daily forecast reconciles exactly to 48 interval rows;
- draft scenarios are excluded and approved scenarios retain the complete BASE
  horizon outside their changed scope;
- capacity uses only approved interval forecasts and one active approved policy;
- weekly supply is recursive and hiring waves honor lead times, yield, FTE per
  head, and training-seat limits;
- supply publication fails when approved hiring-wave FTE does not reconcile;
- refresh and model validation still pass after the Python cells are saved.

Set the Python release gate to passed only after this evidence exists. Never
label the workbook operational merely because the cells were inserted.
