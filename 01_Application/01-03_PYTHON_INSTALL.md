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
5. `scheduling.py` — anonymous pattern fitting and interval coverage.
6. `leave.py` — interval leave-capacity ceilings.
7. `roster.py` — deterministic named assignment and complete-roster validation.
8. `leave_requests.py` — stable full-request leave recommendation queue.
9. `swaps.py` — bilateral whole-occurrence swap simulation.
10. `excel_adapter.py` — DataFrame-to-record boundary only.

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

## Install schedule and coverage entrypoints

After approved requirements refresh, install this Python cell at
`93E_PY_SCHEDULE!B15` and return the schedule candidate:

```python
parameters = xl("tblParameters[#All]", headers=True)
schedule_candidates, schedule_coverage_candidates = run_schedule_excel(
    xl("out_ApprovedRequirementPlan[#All]", headers=True),
    xl("tblShiftPatterns[#All]", headers=True),
    xl("tblShiftRules[#All]", headers=True),
    profile=str(parameter_value_excel(parameters, "EnterpriseProfile")),
)
pd.DataFrame(schedule_candidates)
```

At `93F_PY_COVERAGE!B15`, expose the coverage half of that same deterministic
run for review:

```python
pd.DataFrame(schedule_coverage_candidates)
```

The output is anonymous pattern count, not a named-agent roster. Review the
pattern mix, uncovered and overcovered FTE intervals, cross-midnight effects,
and the `GREEDY_DEFICIT_V1` method. The method is deterministic and transparent;
it is not globally optimal. Paste reviewed pattern rows into
`tblSchedulePlanVersions` on `89A_SCHEDULE_APPROVAL`, add one stable schedule
version and complete approval evidence, then refresh. Power Query independently
recomputes pattern hours and expands approved rows into
`out_ApprovedScheduleCoverage`.

## Install leave-capacity entrypoint

Only after approved schedule coverage refreshes, install this Python cell at
`93G_PY_LEAVE!B15`:

```python
parameters = xl("tblParameters[#All]", headers=True)
leave_candidates = run_leave_excel(
    xl("out_ApprovedScheduleCoverage[#All]", headers=True),
    xl("tblLeavePolicies[#All]", headers=True),
    profile=str(parameter_value_excel(parameters, "EnterpriseProfile")),
)
pd.DataFrame(leave_candidates)
```

Review the calculated interval ceilings and paste only the selected allowance
rows into `tblLeavePlanVersions` on `89B_LEAVE_APPROVAL`, with a stable leave
version, the exact approved schedule version, and complete evidence. An
approved allowance may be between zero and the calculated ceiling. This module
does not contain employee leave requests, balances, identities, or decisions.

## Install named-roster entrypoints

Only after one complete `BASE` schedule version and its leave-capacity plan are
approved, install this cell at `93H_PY_ROSTER!B15`:

```python
parameters = xl("tblParameters[#All]", headers=True)
roster_candidates = run_roster_excel(
    xl("out_ApprovedSchedulePlan[#All]", headers=True),
    xl("tblShiftPatterns[#All]", headers=True),
    xl("out_ApprovedScheduleCoverage[#All]", headers=True),
    xl("tblPeople[#All]", headers=True),
    xl("tblRosterPolicies[#All]", headers=True),
    xl("tblAgentContracts[#All]", headers=True),
    xl("tblActivityEligibility[#All]", headers=True),
    xl("tblAgentSkills[#All]", headers=True),
    xl("tblActivitySkills[#All]", headers=True),
    xl("tblAgentAvailability[#All]", headers=True),
    xl("tblAgentPreferences[#All]", headers=True),
    profile=str(parameter_value_excel(parameters, "EnterpriseProfile")),
)
pd.DataFrame(roster_candidates)
```

Expose the companion results in manifest order:

```python
# 93I_PY_ROSTER_SEGMENTS!B15
pd.DataFrame(roster_segment_candidates)

# 93J_PY_ROSTER_DQ!B15
pd.DataFrame(roster_diagnostic_candidates)

# 93K_PY_ROSTER_PERIODS!B15
pd.DataFrame(roster_period_candidates)
```

Resolve every blocking diagnostic and review period minima/fairness before
copying selected rows to `tblRosterPlanVersions`. Add stable roster and row
keys plus complete approval evidence. Only pseudonymous `AgentKey` may enter
the approval table. The bounded method is deterministic, not globally optimal,
and its configured contract values still require local labor/legal review.

## Install swap and named-leave entrypoints

At `93N_PY_SWAPS!B15`, validate submitted bilateral whole-occurrence swaps:

```python
parameters = xl("tblParameters[#All]", headers=True)
swap_candidates = run_swaps_excel(
    xl("out_ApprovedRoster[#All]", headers=True),
    xl("out_ApprovedSchedulePlan[#All]", headers=True),
    xl("tblShiftPatterns[#All]", headers=True),
    xl("tblSwapRequests[#All]", headers=True),
    xl("tblPeople[#All]", headers=True),
    xl("tblRosterPolicies[#All]", headers=True),
    xl("tblAgentContracts[#All]", headers=True),
    xl("tblActivityEligibility[#All]", headers=True),
    xl("tblAgentSkills[#All]", headers=True),
    xl("tblActivitySkills[#All]", headers=True),
    xl("tblAgentAvailability[#All]", headers=True),
    profile=str(parameter_value_excel(parameters, "EnterpriseProfile")),
)
pd.DataFrame(swap_candidates)
```

Expose `swap_proposal_candidates` at `93O_PY_SWAP_PROPOSALS!B15` and
`swap_diagnostic_candidates` at `93P_PY_SWAP_DQ!B15`. Copy reviewed decisions
to `tblSwapDecisions`; Python cannot approve them.

After the approved swap-decision version refreshes, calculate leave at
`93L_PY_LEAVE_REQUESTS!B15`. This order is mandatory because leave is evaluated
against the effective post-swap assignment:

```python
parameters = xl("tblParameters[#All]", headers=True)
leave_request_candidates = run_leave_requests_excel(
    xl("out_ApprovedRoster[#All]", headers=True),
    xl("out_ApprovedSchedulePlan[#All]", headers=True),
    xl("tblShiftPatterns[#All]", headers=True),
    xl("out_ApprovedLeavePlan[#All]", headers=True),
    xl("tblLeaveRequests[#All]", headers=True),
    xl("tblLeaveTypePolicies[#All]", headers=True),
    xl("tblLeaveEntitlementSnapshots[#All]", headers=True),
    xl("tblLeaveRequestDecisions[#All]", headers=True),
    xl("tblSwapDecisions[#All]", headers=True),
    profile=str(parameter_value_excel(parameters, "EnterpriseProfile")),
)
pd.DataFrame(leave_request_candidates)
```

Expose `leave_consumption_candidates` at
`93M_PY_LEAVE_CONSUMPTION!B15`. Copy reviewed decisions to
`tblLeaveRequestDecisions`, preserving the swap-decision lineage. The engine
supports full-request decisions only. `ALWAYS_REVIEW` categories require human
review and are never capacity-declined.

## Publish with one schedule authority

Approve one row in `tblRosterPublications`, with the exact roster, swap, and
leave decision versions, then complete controlled publication evidence.
Power Query creates `out_PublishedRosterSegments`. Approve exactly one
non-overlapping row in `tblScheduleAuthority`: `IMPORTED_SCHEDULE`, or
`PUBLISHED_ROSTER` with the exact roster and publication versions. Do not enable
published authority until `dq_RosterPublication` and the complete desktop
release checklist pass.

## Release evidence

Record screenshots or exported evidence showing:

- all 27 manifest cells calculate without errors;
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
- schedule fitting is repeatable, keeps infeasible coverage visible, and
  preserves half-open cross-midnight pattern semantics;
- draft schedule rows cannot enter facts and approved pattern hours are
  independently recomputed before schedule coverage is published;
- leave candidates consume only approved schedule coverage and approved leave
  allowance never exceeds the recomputed interval ceiling;
- named assignment is repeatable, leaves every infeasible occurrence visible,
  and excludes display names and business IDs from output;
- approved swaps pass whole-roster revalidation, named leave consumes the
  effective post-swap roster, and publication preserves every version key;
- imported and published schedules are never combined for one effective
  activity/date scope;
- refresh and model validation still pass after the Python cells are saved.

Set the Python release gate to passed only after this evidence exists. Never
label the workbook operational merely because the cells were inserted.
