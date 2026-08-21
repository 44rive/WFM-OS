# Windows Excel installer

`Install-WfmOsExcel.ps1` is a conservative COM preflight and source installer
for Microsoft 365 desktop Excel on Windows. It never modifies the committed
workbook directly and never promotes a release to operational status.

## Safe default: preflight only

Run from PowerShell on Windows:

```powershell
powershell.exe -NoProfile -File tools\windows\Install-WfmOsExcel.ps1
```

Without `-Apply`, the script opens the source workbook read-only, validates the
versioned contract, workbook provenance, required table schemas, query manifest,
and source coverage, then writes a JSON report under the current user's temp
directory. It does not copy, save, import, refresh, or overwrite anything.

## Install query definitions on a copy

```powershell
powershell.exe -NoProfile -File tools\windows\Install-WfmOsExcel.ps1 `
  -Apply `
  -OutputWorkbookPath C:\WFM_OS\Prepared\WFM_OS.prepared.xlsx
```

Existing outputs or queries cause a hard failure unless their corresponding
explicit switches are supplied:

- `-OverwriteOutput`
- `-OverwriteQueries`
- `-OverwriteVbaModule`

The installer adds M definitions in the exact order declared by
`90_Source_Code/01_Power_Query/MANIFEST.csv`. It does not claim to automate
query load destinations, Data Model relationships, Date Table marking, or DAX
measures. Python in Excel cells are also a controlled manual step. These remain
`MANUAL_REQUIRED` in every install report.

The manual model contract is still machine-readable:

- `90_Source_Code/02_DAX/RELATIONSHIPS.csv` declares every relationship;
- `90_Source_Code/02_DAX/MANIFEST.csv` declares every governed measure;
- `90_Source_Code/03_Python/MANIFEST.csv` declares every Python cell and its
  required calculation order;
- `dim_Date[Date]` is the required Date Table contract.

Follow `01_Application/01-02_DESKTOP_RELEASE_CHECKLIST.md` after definition
installation, and use `01_Application/01-03_PYTHON_INSTALL.md` for the Python
cells. `-WhatIf` exercises the apply decision without creating a copy.

## Optional reviewed macro import

```powershell
powershell.exe -NoProfile -File tools\windows\Install-WfmOsExcel.ps1 `
  -Apply `
  -ImportMacro `
  -OutputWorkbookPath C:\WFM_OS\Prepared\WFM_OS.prepared.xlsm
```

`.xlsm` output is permitted only with `-ImportMacro`. The installer tests access
to `Workbook.VBProject` before importing `modCloseDay.bas`; if "Trust access to
the VBA project object model" is unavailable, it fails without publishing the
candidate workbook. Macros are disabled while source workbooks are opened.

## Interpreting the report

A successful definition import ends as `INSTALLED_DEFINITIONS_MANUAL_REQUIRED`,
not `OPERATIONAL`. Review source hashes, query actions, manual requirements, and
the preserved `NOT OPERATIONAL` workbook state before completing the desktop
Excel release checklist.

The script is designed for Windows PowerShell 5.1 and late-bound Excel COM. The
repository CI validates its static safety contract on Linux, but only a run in
the supported desktop Excel environment can validate COM behavior and the
installed workbook.
