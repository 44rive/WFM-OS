# Application workbook

`WFM_OS.xlsx` is the data-free WFM OS application shell. It establishes the
numbered, vendor-neutral workbook structure and the Obsidian & Pearl interface
for the complete workforce-management cycle.

The shell contains:

- business pages from strategic planning through incentive control;
- a command center, Data Quality surface, and refresh audit;
- controlled configuration and decision-input tables;
- exact workbook tables for the repository configuration contracts, including
  `tblParameters`, `tblSourceSystems`, `tblFieldMapping`, `tblValueMapping`,
  `tblPeople`, `tblIdentityMapping`, `tblActivities`, `tblQueueMapping`,
  `tblStateMapping`, `tblMetricRules`, `tblCalendarEvents`,
  `tblForecastPolicies`, `tblIntradayProfiles`, `tblCapacityPolicies`, and
  `tblHiringPolicies`;
- controlled forecast, requirement, supply-assumption, hiring, and supply-plan
  tables;
- controlled close-day input, bounded snapshot-ready output, and an append-only
  snapshot-store reservation;
- hidden, clearly labelled reservations for future analytical and technical
  components;
- `BUILD_INFO`, which identifies the source commit, contract/design versions,
  data state, and executable-engine state.

## Important release boundary

This `.xlsx` is an application shell, not yet an operational WFM calculation
engine. It does not contain embedded Power Query, Power Pivot, DAX, Python in
Excel, or VBA. The workbook and `BUILD_INFO` state this explicitly. Those
components must be installed and tested in desktop Excel before creating the
first genuine `.xlsm` release.

No production data belongs in the committed workbook.

## Rebuild

From the repository root:

```bash
python3 -m pip install -r requirements-build.txt
python3 tools/build_workbook.py --build-date YYYY-MM-DD
python3 tools/validate_workbook.py
```

For release builds, supply an explicit build date. The generator records the
current Git commit automatically and normalizes OOXML timestamps, so identical
inputs produce an identical workbook. `BUILD_PROVENANCE.json` records the exact
release inputs and SHA-256 checksum; CI rebuilds the file and compares its bytes.

## Desktop Excel release gate

Before promoting this shell to `WFM_OS.xlsm`:

1. install genuine Power Query adapters and canonical queries from
   `90_Source_Code/01_Power_Query/`;
2. build and reconcile the Power Pivot model and explicit DAX measures;
3. install genuine Python in Excel cells in the declared calculation order;
4. add only the minimal controlled VBA modules required for refresh, backup,
   snapshot, and publication;
5. refresh twice with anonymized fixtures and complete the technical and visual
   checks in `AI_GUIDE.md`;
6. update `BUILD_INFO` and commit source and workbook together.
