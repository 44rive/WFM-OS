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
3. `excel_adapter.py` — DataFrame-to-record boundary only.

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
Review accuracy, document the method and source run, reconcile the daily total
to an approved intraday profile, and paste the resulting interval rows into
`tblForecastVersions` on `85_FORECAST_APPROVAL`. Approval metadata is mandatory.

## Install capacity entrypoint

After approved interval forecasts refresh into `out_ApprovedForecast`, install
this Python cell at `93_PY_SCENARIOS!B15` and return an Excel value:

```python
parameters = xl("tblParameters[#All]", headers=True)
capacity_candidates = run_capacity_excel(
    xl("out_ApprovedForecast[#All]", headers=True),
    xl("tblCapacityPolicies[#All]", headers=True),
    profile=str(parameter_value_excel(parameters, "EnterpriseProfile")),
)
pd.DataFrame(capacity_candidates)
```

Review and reconcile these candidates, then paste the approved interval rows
into `tblRequirementApprovals` on `86_REQUIREMENT_APPROVAL`. Only valid approved
rows enter the canonical staffing-requirement facts.

## Release evidence

Record screenshots or exported evidence showing:

- all five manifest cells calculate without errors;
- the two output DataFrames have stable headers and nonnegative values;
- future history beyond `p_AsOfDate` does not affect the forecast;
- a draft forecast cannot become a canonical fact;
- capacity uses only approved interval forecasts and one active approved policy;
- refresh and model validation still pass after the Python cells are saved.

Set the Python release gate to passed only after this evidence exists. Never
label the workbook operational merely because the cells were inserted.
