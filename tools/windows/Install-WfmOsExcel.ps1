#requires -Version 5.1

[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "Medium")]
param(
    [string]$RepositoryRoot,
    [switch]$Apply,
    [string]$OutputWorkbookPath,
    [switch]$OverwriteOutput,
    [switch]$OverwriteQueries,
    [switch]$ImportMacro,
    [switch]$OverwriteVbaModule,
    [string]$ReportPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-AbsolutePath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$BasePath
    )

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $BasePath $Path))
}

function Assert-File {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not [System.IO.File]::Exists($Path)) {
        throw "Required file does not exist: $Path"
    }
}

function Release-ComObject {
    param($Object)

    if ($null -ne $Object -and [System.Runtime.InteropServices.Marshal]::IsComObject($Object)) {
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($Object)
    }
}

function Get-WorkbookTables {
    param([Parameter(Mandatory = $true)]$Workbook)

    $tables = @{}
    foreach ($worksheet in @($Workbook.Worksheets)) {
        try {
            foreach ($table in @($worksheet.ListObjects)) {
                try {
                    $columns = @()
                    for ($index = 1; $index -le $table.ListColumns.Count; $index++) {
                        $column = $table.ListColumns.Item($index)
                        try {
                            $columns += [string]$column.Name
                        }
                        finally {
                            Release-ComObject $column
                        }
                    }
                    if ($tables.ContainsKey([string]$table.Name)) {
                        throw "Duplicate workbook table name: $($table.Name)"
                    }
                    $tables[[string]$table.Name] = [pscustomobject]@{
                        Sheet = [string]$worksheet.Name
                        Columns = $columns
                    }
                }
                finally {
                    Release-ComObject $table
                }
            }
        }
        finally {
            Release-ComObject $worksheet
        }
    }
    return $tables
}

function Get-WorkbookTable {
    param(
        [Parameter(Mandatory = $true)]$Workbook,
        [Parameter(Mandatory = $true)][string]$Name
    )

    foreach ($worksheet in @($Workbook.Worksheets)) {
        try {
            foreach ($table in @($worksheet.ListObjects)) {
                if ([string]$table.Name -ceq $Name) {
                    return $table
                }
                Release-ComObject $table
            }
        }
        finally {
            Release-ComObject $worksheet
        }
    }
    return $null
}

function Assert-WorkbookContract {
    param(
        [Parameter(Mandatory = $true)]$Workbook,
        [Parameter(Mandatory = $true)]$Contract
    )

    $tables = Get-WorkbookTables -Workbook $Workbook
    foreach ($requiredTable in @($Contract.requiredWorkbookTables)) {
        $name = [string]$requiredTable.name
        if (-not $tables.ContainsKey($name)) {
            throw "Required workbook table is missing: $name"
        }
        $actual = @($tables[$name].Columns)
        $expected = @($requiredTable.columns | ForEach-Object { [string]$_ })
        if ($actual.Count -ne $expected.Count) {
            throw "Column count mismatch for $name. Expected $($expected.Count), found $($actual.Count)."
        }
        for ($index = 0; $index -lt $expected.Count; $index++) {
            if ($actual[$index] -cne $expected[$index]) {
                throw "Column mismatch for $name at position $($index + 1). Expected '$($expected[$index])', found '$($actual[$index])'."
            }
        }
    }

    $buildTable = Get-WorkbookTable -Workbook $Workbook -Name "tblBuildInfo"
    try {
        $buildValues = @{}
        if ($null -eq $buildTable.DataBodyRange) {
            throw "tblBuildInfo has no data rows."
        }
        for ($row = 1; $row -le $buildTable.DataBodyRange.Rows.Count; $row++) {
            $field = [string]$buildTable.DataBodyRange.Cells.Item($row, 1).Value2
            $value = [string]$buildTable.DataBodyRange.Cells.Item($row, 2).Value2
            $buildValues[$field] = $value
        }
        if ($buildValues["Release"] -cne [string]$Contract.workbookRelease) {
            throw "Workbook release does not match installer contract."
        }
        if ($buildValues["Operational status"] -cne "NOT OPERATIONAL") {
            throw "Input workbook must remain explicitly NOT OPERATIONAL."
        }
        if ($buildValues["Power Query"] -cne "NOT EMBEDDED") {
            throw "Input workbook already claims a Power Query state outside this installer contract."
        }
    }
    finally {
        Release-ComObject $buildTable
    }

    return $tables
}

function Set-BuildInfoValue {
    param(
        [Parameter(Mandatory = $true)]$BuildTable,
        [Parameter(Mandatory = $true)][string]$Field,
        [Parameter(Mandatory = $true)][string]$Value,
        [Parameter(Mandatory = $true)][string]$Evidence
    )

    for ($row = 1; $row -le $BuildTable.DataBodyRange.Rows.Count; $row++) {
        if ([string]$BuildTable.DataBodyRange.Cells.Item($row, 1).Value2 -ceq $Field) {
            $BuildTable.DataBodyRange.Cells.Item($row, 2).Value2 = $Value
            $BuildTable.DataBodyRange.Cells.Item($row, 3).Value2 = $Evidence
            return
        }
    }
    throw "BUILD_INFO field is missing: $Field"
}

function Get-WorkbookQuery {
    param(
        [Parameter(Mandatory = $true)]$Workbook,
        [Parameter(Mandatory = $true)][string]$Name
    )

    foreach ($query in @($Workbook.Queries)) {
        if ([string]$query.Name -ceq $Name) {
            return $query
        }
        Release-ComObject $query
    }
    return $null
}

function Get-VbaComponent {
    param(
        [Parameter(Mandatory = $true)]$VbaProject,
        [Parameter(Mandatory = $true)][string]$Name
    )

    foreach ($component in @($VbaProject.VBComponents)) {
        if ([string]$component.Name -ceq $Name) {
            return $component
        }
        Release-ComObject $component
    }
    return $null
}

function Write-InstallReport {
    param(
        [Parameter(Mandatory = $true)]$Report,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $parent = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($parent)) {
        [System.IO.Directory]::CreateDirectory($parent) | Out-Null
    }
    $Report.completedAtUtc = [DateTime]::UtcNow.ToString("o")
    $Report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Path -Encoding UTF8
}

if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw "This installer requires Windows and desktop Excel."
}

if ([string]::IsNullOrWhiteSpace($RepositoryRoot)) {
    $RepositoryRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
}
$RepositoryRoot = [System.IO.Path]::GetFullPath($RepositoryRoot)

$contractPath = Join-Path $PSScriptRoot "installer-contract.json"
Assert-File $contractPath
$contract = Get-Content -LiteralPath $contractPath -Raw -Encoding UTF8 | ConvertFrom-Json

if ([string]::IsNullOrWhiteSpace($ReportPath)) {
    $reportName = "WFM_OS_install_{0}.json" -f [DateTime]::UtcNow.ToString("yyyyMMdd_HHmmss_fff")
    $ReportPath = Join-Path ([System.IO.Path]::GetTempPath()) $reportName
}
else {
    $ReportPath = Resolve-AbsolutePath -Path $ReportPath -BasePath $RepositoryRoot
}

$inputWorkbook = Resolve-AbsolutePath -Path ([string]$contract.inputArtifact) -BasePath $RepositoryRoot
$provenancePath = Resolve-AbsolutePath -Path ([string]$contract.buildProvenance) -BasePath $RepositoryRoot
$queryManifestPath = Resolve-AbsolutePath -Path ([string]$contract.queryManifest) -BasePath $RepositoryRoot
$daxManifestPath = Resolve-AbsolutePath -Path ([string]$contract.daxManifest) -BasePath $RepositoryRoot
$relationshipManifestPath = Resolve-AbsolutePath -Path ([string]$contract.relationshipManifest) -BasePath $RepositoryRoot

$report = [ordered]@{
    contractVersion = [string]$contract.contractVersion
    installerVersion = [string]$contract.installerVersion
    startedAtUtc = [DateTime]::UtcNow.ToString("o")
    completedAtUtc = $null
    mode = $(if ($Apply) { "APPLY" } else { "PREFLIGHT" })
    status = "STARTED"
    repositoryRoot = $RepositoryRoot
    inputWorkbook = $inputWorkbook
    outputWorkbook = $null
    reportPath = $ReportPath
    sourceSha256 = $null
    sourceGitCommit = $null
    excelVersion = $null
    excelBuild = $null
    queryActions = @()
    vbaActions = @()
    modelContract = [ordered]@{
        daxManifest = [string]$contract.daxManifest
        relationshipManifest = [string]$contract.relationshipManifest
        dateTable = $contract.dateTable
        measureCount = 0
        relationshipCount = 0
        installation = "MANUAL_REQUIRED"
    }
    manualRequiredCapabilities = @($contract.manualRequiredCapabilities)
    errors = @()
}

$excel = $null
$workbook = $null
$tables = $null
$stageXlsx = $null
$stageXlsm = $null
$vbaProject = $null
$failure = $null

try {
    Assert-File $inputWorkbook
    Assert-File $provenancePath
    Assert-File $queryManifestPath
    Assert-File $daxManifestPath
    Assert-File $relationshipManifestPath

    $provenance = Get-Content -LiteralPath $provenancePath -Raw -Encoding UTF8 | ConvertFrom-Json
    $sourceHash = (Get-FileHash -LiteralPath $inputWorkbook -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($sourceHash -cne ([string]$provenance.sha256).ToLowerInvariant()) {
        throw "Input workbook SHA-256 does not match BUILD_PROVENANCE.json."
    }
    if ([string]$provenance.release -cne [string]$contract.workbookRelease) {
        throw "Provenance release does not match installer contract."
    }
    $report.sourceSha256 = $sourceHash
    $report.sourceGitCommit = [string]$provenance.git_commit

    foreach ($relativePath in @($contract.manualSourceFiles) + @($contract.vbaModules)) {
        Assert-File (Resolve-AbsolutePath -Path ([string]$relativePath) -BasePath $RepositoryRoot)
    }

    $manifest = @(Import-Csv -LiteralPath $queryManifestPath)
    if ($manifest.Count -eq 0) {
        throw "Power Query manifest is empty."
    }
    $seenOrders = @{}
    $seenNames = @{}
    $previousOrder = [int]::MinValue
    $listedSources = @{}
    foreach ($row in $manifest) {
        $order = 0
        if (-not [int]::TryParse([string]$row.InstallOrder, [ref]$order)) {
            throw "Invalid query InstallOrder: $($row.InstallOrder)"
        }
        if ($order -le $previousOrder) {
            throw "Power Query manifest must be strictly ordered."
        }
        if ($seenOrders.ContainsKey($order) -or $seenNames.ContainsKey([string]$row.QueryName)) {
            throw "Duplicate query order or name in Power Query manifest."
        }
        if ([string]$row.LoadDestination -notmatch '^(ConnectionOnly|DataModel|Worksheet:[^!]+![^!]+)$') {
            throw "Unsupported load destination for $($row.QueryName): $($row.LoadDestination)"
        }
        $querySourcePath = Resolve-AbsolutePath -Path ([string]$row.SourceFile) -BasePath (Split-Path -Parent $queryManifestPath)
        Assert-File $querySourcePath
        if ([System.IO.Path]::GetFileNameWithoutExtension($querySourcePath) -cne [string]$row.QueryName) {
            throw "Query source filename does not match QueryName: $querySourcePath"
        }
        $seenOrders[$order] = $true
        $seenNames[[string]$row.QueryName] = $true
        $listedSources[$querySourcePath.ToLowerInvariant()] = $true
        $previousOrder = $order
    }
    $querySourceRoot = Split-Path -Parent $queryManifestPath
    foreach ($source in @(Get-ChildItem -LiteralPath $querySourceRoot -Recurse -File -Filter "*.pq")) {
        if (-not $listedSources.ContainsKey($source.FullName.ToLowerInvariant())) {
            throw "Power Query source is missing from MANIFEST.csv: $($source.FullName)"
        }
    }

    $modelTables = @{}
    foreach ($row in $manifest) {
        if ([string]$row.LoadDestination -ceq "DataModel") {
            $modelTables[[string]$row.QueryName] = $true
        }
    }

    $daxManifest = @(Import-Csv -LiteralPath $daxManifestPath)
    if ($daxManifest.Count -eq 0) {
        throw "DAX manifest is empty."
    }
    $seenMeasureOrders = @{}
    $seenMeasureNames = @{}
    foreach ($measure in $daxManifest) {
        $order = 0
        if (-not [int]::TryParse([string]$measure.InstallOrder, [ref]$order)) {
            throw "Invalid DAX InstallOrder: $($measure.InstallOrder)"
        }
        $measureName = [string]$measure.MeasureName
        if ($seenMeasureOrders.ContainsKey($order) -or $seenMeasureNames.ContainsKey($measureName)) {
            throw "Duplicate measure order or name in DAX manifest."
        }
        if (-not $modelTables.ContainsKey([string]$measure.HomeTable)) {
            throw "DAX home table is not declared for Data Model load: $($measure.HomeTable)"
        }
        if ([string]::IsNullOrWhiteSpace([string]$measure.FormatString)) {
            throw "DAX measure has no format string: $measureName"
        }
        $daxSourcePath = Resolve-AbsolutePath -Path ([string]$measure.SourceFile) -BasePath (Split-Path -Parent $daxManifestPath)
        Assert-File $daxSourcePath
        $daxSource = Get-Content -LiteralPath $daxSourcePath -Raw -Encoding UTF8
        $measurePattern = '(?m)^' + [regex]::Escape($measureName) + '\s*:=\s*$'
        if ($daxSource -notmatch $measurePattern) {
            throw "DAX measure is not present in its declared source file: $measureName"
        }
        $seenMeasureOrders[$order] = $true
        $seenMeasureNames[$measureName] = $true
    }

    $relationshipManifest = @(Import-Csv -LiteralPath $relationshipManifestPath)
    if ($relationshipManifest.Count -eq 0) {
        throw "Relationship manifest is empty."
    }
    $seenRelationshipOrders = @{}
    $seenRelationships = @{}
    foreach ($relationship in $relationshipManifest) {
        $order = 0
        if (-not [int]::TryParse([string]$relationship.InstallOrder, [ref]$order)) {
            throw "Invalid relationship InstallOrder: $($relationship.InstallOrder)"
        }
        $relationshipKey = @(
            [string]$relationship.ForeignTable,
            [string]$relationship.ForeignColumn,
            [string]$relationship.LookupTable,
            [string]$relationship.LookupColumn
        ) -join "|"
        if ($seenRelationshipOrders.ContainsKey($order) -or $seenRelationships.ContainsKey($relationshipKey)) {
            throw "Duplicate relationship order or key in relationship manifest."
        }
        if (-not $modelTables.ContainsKey([string]$relationship.ForeignTable) -or
            -not $modelTables.ContainsKey([string]$relationship.LookupTable)) {
            throw "Relationship table is not declared for Data Model load: $relationshipKey"
        }
        if ([string]$relationship.Cardinality -cne "ManyToOne" -or
            [string]$relationship.CrossFilter -cne "Single" -or
            [string]$relationship.Active -cne "TRUE") {
            throw "Relationship must be active, many-to-one, and single-direction: $relationshipKey"
        }
        $seenRelationshipOrders[$order] = $true
        $seenRelationships[$relationshipKey] = $true
    }
    if (-not $modelTables.ContainsKey([string]$contract.dateTable.table) -or
        [string]::IsNullOrWhiteSpace([string]$contract.dateTable.column)) {
        throw "Date Table contract is incomplete or does not target a Data Model table."
    }
    $report.modelContract.measureCount = $daxManifest.Count
    $report.modelContract.relationshipCount = $relationshipManifest.Count

    if ($ImportMacro -and -not $Apply) {
        throw "-ImportMacro requires -Apply."
    }
    if ($Apply -and [string]::IsNullOrWhiteSpace($OutputWorkbookPath)) {
        throw "-OutputWorkbookPath is required with -Apply."
    }
    if (-not $Apply -and -not [string]::IsNullOrWhiteSpace($OutputWorkbookPath)) {
        throw "-OutputWorkbookPath is only valid with -Apply."
    }

    $outputPath = $null
    if ($Apply) {
        $outputPath = Resolve-AbsolutePath -Path $OutputWorkbookPath -BasePath $RepositoryRoot
        $report.outputWorkbook = $outputPath
        if ($outputPath -ieq $inputWorkbook) {
            throw "The committed input workbook cannot be used as the output path."
        }
        $extension = [System.IO.Path]::GetExtension($outputPath).ToLowerInvariant()
        $expectedExtension = $(if ($ImportMacro) { ".xlsm" } else { ".xlsx" })
        if ($extension -cne $expectedExtension) {
            throw "Output extension must be $expectedExtension for the selected options."
        }
        if ([System.IO.File]::Exists($outputPath) -and -not $OverwriteOutput) {
            throw "Output already exists. Use -OverwriteOutput to replace it after a successful staged install."
        }
    }

    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.EnableEvents = $false
    $excel.AutomationSecurity = 3
    $report.excelVersion = [string]$excel.Version
    $report.excelBuild = [string]$excel.Build
    $excelMajor = 0
    [void][int]::TryParse(([string]$excel.Version).Split('.')[0], [ref]$excelMajor)
    if ($excelMajor -lt 16) {
        throw "Excel 2016 or later is required; Microsoft 365 desktop Excel is the supported release environment."
    }

    $workbook = $excel.Workbooks.Open($inputWorkbook, 0, $true)
    $tables = Assert-WorkbookContract -Workbook $workbook -Contract $contract
    $workbook.Close($false)
    Release-ComObject $workbook
    $workbook = $null
    $tables = $null

    if (-not $Apply) {
        $report.status = "PREFLIGHT_PASSED_MANUAL_REQUIRED"
    }
    elseif (-not $PSCmdlet.ShouldProcess($outputPath, "Create a staged WFM OS workbook and install reviewed source definitions")) {
        $report.status = "PREFLIGHT_PASSED_WHATIF"
    }
    else {
        $outputDirectory = Split-Path -Parent $outputPath
        [System.IO.Directory]::CreateDirectory($outputDirectory) | Out-Null
        $stageBase = ".{0}.wfmstage.{1}" -f [System.IO.Path]::GetFileNameWithoutExtension($outputPath), [guid]::NewGuid().ToString("N")
        $stageXlsx = Join-Path $outputDirectory ($stageBase + ".xlsx")
        [System.IO.File]::Copy($inputWorkbook, $stageXlsx, $false)

        $workbook = $excel.Workbooks.Open($stageXlsx, 0, $false)
        $tables = Assert-WorkbookContract -Workbook $workbook -Contract $contract

        $queryConflicts = @()
        foreach ($row in $manifest) {
            $existing = Get-WorkbookQuery -Workbook $workbook -Name ([string]$row.QueryName)
            if ($null -ne $existing) {
                $queryConflicts += [string]$row.QueryName
                Release-ComObject $existing
            }
        }
        if ($queryConflicts.Count -gt 0 -and -not $OverwriteQueries) {
            throw "Queries already exist in the candidate: $($queryConflicts -join ', '). Use -OverwriteQueries to replace them."
        }

        foreach ($row in $manifest) {
            $queryName = [string]$row.QueryName
            $querySourcePath = Resolve-AbsolutePath -Path ([string]$row.SourceFile) -BasePath (Split-Path -Parent $queryManifestPath)
            $formula = Get-Content -LiteralPath $querySourcePath -Raw -Encoding UTF8
            $existing = Get-WorkbookQuery -Workbook $workbook -Name $queryName
            $action = "ADDED"
            if ($null -ne $existing) {
                $existing.Delete()
                Release-ComObject $existing
                $action = "REPLACED"
            }
            $description = "WFM OS canonical source: $($row.SourceFile)"
            $created = $workbook.Queries.Add($queryName, $formula, $description)
            Release-ComObject $created
            $report.queryActions += [ordered]@{
                installOrder = [int]$row.InstallOrder
                name = $queryName
                action = $action
                sourceFile = [string]$row.SourceFile
                sourceSha256 = (Get-FileHash -LiteralPath $querySourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
                declaredLoadDestination = [string]$row.LoadDestination
                loadInstallation = "MANUAL_REQUIRED"
            }
        }

        $buildTable = Get-WorkbookTable -Workbook $workbook -Name "tblBuildInfo"
        try {
            Set-BuildInfoValue -BuildTable $buildTable -Field "Build type" -Value "PREPARED CANDIDATE" -Evidence "Definitions installed by reviewed Windows installer; desktop validation incomplete"
            Set-BuildInfoValue -BuildTable $buildTable -Field "Power Query" -Value "DEFINITIONS INSTALLED" -Evidence "Load destinations and refresh remain MANUAL_REQUIRED"
            Set-BuildInfoValue -BuildTable $buildTable -Field "Operational status" -Value "NOT OPERATIONAL" -Evidence "Desktop engine validation and release approval are still required"
        }
        finally {
            Release-ComObject $buildTable
        }

        if ($ImportMacro) {
            try {
                $vbaProject = $workbook.VBProject
                $probe = $vbaProject.VBComponents.Count
            }
            catch {
                throw "Excel denied access to Workbook.VBProject. Review Trust Center policy before using -ImportMacro."
            }

            foreach ($relativeModulePath in @($contract.vbaModules)) {
                $modulePath = Resolve-AbsolutePath -Path ([string]$relativeModulePath) -BasePath $RepositoryRoot
                $moduleName = [System.IO.Path]::GetFileNameWithoutExtension($modulePath)
                $existingModule = Get-VbaComponent -VbaProject $vbaProject -Name $moduleName
                if ($null -ne $existingModule -and -not $OverwriteVbaModule) {
                    Release-ComObject $existingModule
                    throw "VBA component already exists: $moduleName. Use -OverwriteVbaModule to replace it."
                }
                $moduleAction = "IMPORTED"
                if ($null -ne $existingModule) {
                    $vbaProject.VBComponents.Remove($existingModule)
                    Release-ComObject $existingModule
                    $moduleAction = "REPLACED"
                }
                $imported = $vbaProject.VBComponents.Import($modulePath)
                Release-ComObject $imported
                $report.vbaActions += [ordered]@{
                    name = $moduleName
                    action = $moduleAction
                    sourceFile = [string]$relativeModulePath
                    sourceSha256 = (Get-FileHash -LiteralPath $modulePath -Algorithm SHA256).Hash.ToLowerInvariant()
                    executionValidation = "MANUAL_REQUIRED"
                }
            }
            $buildTable = Get-WorkbookTable -Workbook $workbook -Name "tblBuildInfo"
            try {
                Set-BuildInfoValue -BuildTable $buildTable -Field "VBA" -Value "SOURCE IMPORTED" -Evidence "Macro execution and close-day controls remain MANUAL_REQUIRED"
            }
            finally {
                Release-ComObject $buildTable
            }
            $stageXlsm = Join-Path $outputDirectory ($stageBase + ".xlsm")
            $workbook.SaveAs($stageXlsm, 52)
            Release-ComObject $vbaProject
            $vbaProject = $null
        }
        else {
            $workbook.Save()
        }

        $workbook.Close($true)
        Release-ComObject $workbook
        $workbook = $null
        $tables = $null

        $publishStage = $(if ($ImportMacro) { $stageXlsm } else { $stageXlsx })
        if ($ImportMacro -and [System.IO.File]::Exists($stageXlsx)) {
            [System.IO.File]::Delete($stageXlsx)
            $stageXlsx = $null
        }
        if ([System.IO.File]::Exists($outputPath)) {
            [System.IO.File]::Replace($publishStage, $outputPath, $null, $true)
        }
        else {
            [System.IO.File]::Move($publishStage, $outputPath)
        }
        if ($ImportMacro) { $stageXlsm = $null } else { $stageXlsx = $null }
        $report.status = "INSTALLED_DEFINITIONS_MANUAL_REQUIRED"
    }
}
catch {
    $failure = $_.Exception.Message
    $report.errors += $failure
    $report.status = "FAILED"
}
finally {
    if ($null -ne $vbaProject) {
        Release-ComObject $vbaProject
    }
    if ($null -ne $workbook) {
        try { $workbook.Close($false) } catch { }
        Release-ComObject $workbook
    }
    if ($null -ne $excel) {
        try { $excel.Quit() } catch { }
        Release-ComObject $excel
    }
    foreach ($stagePath in @($stageXlsx, $stageXlsm)) {
        if (-not [string]::IsNullOrWhiteSpace([string]$stagePath) -and [System.IO.File]::Exists([string]$stagePath)) {
            try { [System.IO.File]::Delete([string]$stagePath) } catch { }
        }
    }
    Write-InstallReport -Report $report -Path $ReportPath
    Write-Host "WFM OS installer report: $ReportPath"
}

if ($null -ne $failure) {
    throw $failure
}
