# 01-02 · Desktop Excel release checklist

This checklist converts the reproducible `.xlsx` shell into a reviewed desktop
Excel candidate. It is intentionally fail-closed: installing source definitions
does not make the workbook operational.

## Candidate states

| State | Meaning | Permitted use |
|---|---|---|
| `SHELL_NOT_OPERATIONAL` | Clean generated workbook; engines are absent | Review structure and design only |
| `DEFINITIONS_INSTALLED_MANUAL_REQUIRED` | M definitions and optional reviewed VBA source are present | Complete engine wiring on anonymized data |
| `ENGINE_WIRED_NOT_VALIDATED` | Loads, model, relationships, measures, and controls exist | Test and reconcile only |
| `VALIDATED_CANDIDATE` | Technical, fixture, repeat-refresh, and visual evidence passes | Release approval only |
| `OPERATIONAL_RELEASE` | Approved artifact, evidence, version, and hash agree | Governed enterprise use |

No operator or automation may skip a state.

## 1 · Run the safe preflight

From Windows PowerShell with Microsoft 365 desktop Excel installed:

```powershell
powershell.exe -NoProfile -File tools\windows\Install-WfmOsExcel.ps1
```

The command opens the committed shell read-only with macros disabled. It checks
the artifact hash and Git provenance, required table schemas, Power Query source
coverage, model metadata, DAX and Python manifests, and Excel availability.
Preserve the JSON report path printed by the command.

## 2 · Install reviewed definitions on a new copy

```powershell
powershell.exe -NoProfile -File tools\windows\Install-WfmOsExcel.ps1 `
  -Apply `
  -OutputWorkbookPath C:\WFM_OS\Prepared\WFM_OS.prepared.xlsx
```

Use `-WhatIf` for a dry-run of the apply boundary. Existing output is rejected
unless `-OverwriteOutput` is explicit. Replacement is staged and published only
after a successful save. The committed source workbook is never modified.

The expected result is `INSTALLED_DEFINITIONS_MANUAL_REQUIRED`. Any report that
contains `FAILED` or a different source hash blocks the release.

## 3 · Wire Power Query loads

Use `90_Source_Code/01_Power_Query/MANIFEST.csv` as the only source of truth:

1. keep functions, parameters, sources, and staging queries as connection only;
2. load dimensions and facts marked `DataModel` to the Data Model only;
3. load worksheet outputs to the exact sheet and table declared after
   `Worksheet:`;
4. do not load a large fact to a worksheet;
5. confirm every query name, kind, destination, and refresh lane against the
   manifest after saving and reopening the workbook.

Do not use a guessed `Microsoft.Mashup.OleDb.1` connection string as release
evidence. Excel-created connections and load settings must be inspected in the
actual target desktop version.

## 4 · Build the semantic model

1. Refresh dimensions first and confirm lookup keys are unique and nonblank.
2. Refresh facts and reconcile source counts before relationships are created.
3. Create every relationship in
   `90_Source_Code/02_DAX/RELATIONSHIPS.csv` exactly once.
4. Keep relationships active, many-to-one, and single-direction from each
   lookup dimension to its facts.
5. Mark `dim_Date` as the Date Table using `dim_Date[Date]`.
6. Confirm there is no relationship between a live fact and its closed fact.
7. Confirm there is only one active filter path between any dimension and fact.

Capture a model diagram screenshot and an exported relationship inventory as
release evidence.

## 5 · Install governed DAX measures

Use `90_Source_Code/02_DAX/MANIFEST.csv` for order, home table, number format,
display folder, and description. Use the referenced `.dax` file for the formula.

After installation:

1. compare all 80 measure names to the manifest;
2. confirm there are no implicit measures on business pages;
3. test blank and zero denominators for every ratio;
4. validate measures labelled `· Interval` only at 30-minute interval grain;
5. reconcile service, attendance, adherence, staffing, forecast, accuracy,
   schedule coverage, and leave-capacity totals to the golden
   fixture outputs.

## 6 · Install governed Python cells

Follow `01_Application/01-03_PYTHON_INSTALL.md` and install all 27 rows from
`90_Source_Code/03_Python/MANIFEST.csv` in exact order. Confirm each definition
cell calculates before installing the next cell. Capture evidence that the
forecast adapter excludes history after `AsOfDate`, the daily forecast is
reconciled to an interval profile before approval, and the capacity adapter
reads only approved interval forecasts. Also prove weekly supply recursion,
hiring-wave seat splitting and timing, hiring-to-supply reconciliation,
deterministic pattern fitting, cross-midnight coverage, leave-capacity ceilings,
named assignment, bilateral swap revalidation, and the post-swap full-request
leave queue. Prove that leave capacity reads approved Power Query coverage and
that named leave reads the effective approved roster rather than an unapproved
Python spill.

Neither spilled candidate output is a canonical fact. Approval requires stable
keys, source-run evidence, approver, timestamp, and successful
`dq_PlanningApprovals` refresh.

## 7 · Install the controlled close-day action

For the macro-enabled candidate:

```powershell
powershell.exe -NoProfile -File tools\windows\Install-WfmOsExcel.ps1 `
  -Apply `
  -ImportMacro `
  -OutputWorkbookPath C:\WFM_OS\Prepared\WFM_OS.prepared.xlsm
```

VBA project access must be permitted by enterprise policy. The import is not
execution evidence. Assign `CloseOperationalDay` to the controlled action on
`84_CLOSE_DAY`, then prove approval blocking, failed-DQ blocking, replacement
behavior, idempotency, and duplicate prevention with anonymized fixtures.

## 8 · Execute release evidence

All evidence is required:

| Evidence | Pass condition |
|---|---|
| Artifact identity | Candidate source hash and Git commit match the installer report |
| Query inventory | Every manifest row exists with the exact declared load destination |
| Refresh | Shared, live, and closed lanes complete without repair or privacy prompts |
| Data quality | Unknowns remain visible; every blocking check is zero or resolved |
| Reconciliation | Source counts and governed totals tie to the accepted fixture outputs |
| Semantic model | 54 required relationships exist with one intended filter path |
| Measures | 80 explicit measures match name, formula, format, and expected result |
| Planning Python | 27 ordered cells execute; candidate/approval boundaries and as-of behavior pass |
| Planning reconciliation | Daily forecast equals interval totals; requirements trace to forecast/policy; hiring FTE reconciles to supply; schedule coverage and leave ceilings independently recompute; named roster, changes, publication, and schedule authority preserve exact lineage |
| Close day | Approval controls pass; repeat close is idempotent and duplicate-free |
| Repeatability | A second refresh returns identical finalized results |
| Visual inspection | Pages pass the design-system checklist at 100% zoom |
| Security | No credentials, production data, or personal data exist in the artifact or diff |

Contact-service and operational-control evidence may be assessed independently,
but missing Python or planning-approval evidence blocks any whole-product or
planning-cycle operational claim.

## 9 · Promote deliberately

Only after all evidence passes:

1. update `99_BUILD_INFO` to the reviewed release version, exact Git commit,
   engine status, validation date, and `OPERATIONAL` status;
2. save the approved artifact as `01_Application/WFM_OS.xlsm`;
3. calculate and record its SHA-256 outside the workbook;
4. commit source, manifests, evidence metadata, and workbook together;
5. rerun repository CI and archive the clean prior release under `99_Archive/`.

If any engine source or manifest changes, the evidence is stale and the
candidate returns to `DEFINITIONS_INSTALLED_MANUAL_REQUIRED`.
