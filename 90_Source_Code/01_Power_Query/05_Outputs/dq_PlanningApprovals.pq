let
    ForecastIssues = Table.SelectRows(
        stg_ForecastVersions,
        each [ApprovedFlag] and [ValidationStatus] <> "VALID"
    ),
    ForecastEntity = Table.AddColumn(ForecastIssues, "Entity", each "Forecast", type text),
    ForecastRows = Table.SelectColumns(
        ForecastEntity,
        {
            "Entity", "ForecastRowKey", "ForecastVersionKey", "ApprovalStatus",
            "ValidationStatus", "IntervalStart", "ActivityKey", "ChannelKey"
        }
    ),
    ForecastRenamed = Table.RenameColumns(
        ForecastRows,
        {{"ForecastRowKey", "RowKey"}, {"ForecastVersionKey", "VersionKey"}, {"ValidationStatus", "Issue"}}
    ),
    RequirementIssues = Table.SelectRows(
        stg_RequirementApprovals,
        each [ApprovedFlag] and [MappingStatus] <> "MAPPED"
    ),
    RequirementEntity = Table.AddColumn(RequirementIssues, "Entity", each "StaffingRequirement", type text),
    RequirementRows = Table.SelectColumns(
        RequirementEntity,
        {
            "Entity", "RequirementKey", "RequirementVersion", "ApprovalStatus",
            "MappingStatus", "IntervalStart", "ActivityKey", "ChannelKey"
        }
    ),
    RequirementRenamed = Table.RenameColumns(
        RequirementRows,
        {{"RequirementKey", "RowKey"}, {"RequirementVersion", "VersionKey"}, {"MappingStatus", "Issue"}}
    ),
    SupplyIssues = Table.SelectRows(
        stg_SupplyPlanVersions,
        each [ApprovedFlag] and [ValidationStatus] <> "VALID"
    ),
    SupplyEntity = Table.AddColumn(SupplyIssues, "Entity", each "SupplyPlan", type text),
    SupplyChannel = Table.AddColumn(SupplyEntity, "ChannelKey", each null, type nullable text),
    SupplyRows = Table.SelectColumns(
        SupplyChannel,
        {
            "Entity", "PlanRowKey", "PlanVersionKey", "ApprovalStatus",
            "ValidationStatus", "PeriodStart", "ActivityKey", "ChannelKey"
        }
    ),
    SupplyRenamed = Table.RenameColumns(
        SupplyRows,
        {
            {"PlanRowKey", "RowKey"}, {"PlanVersionKey", "VersionKey"},
            {"ValidationStatus", "Issue"}, {"PeriodStart", "IntervalStart"}
        }
    ),
    HiringIssues = Table.SelectRows(
        stg_HiringPlanVersions,
        each [ApprovedFlag] and [ValidationStatus] <> "VALID"
    ),
    HiringEntity = Table.AddColumn(HiringIssues, "Entity", each "HiringPlan", type text),
    HiringChannel = Table.AddColumn(HiringEntity, "ChannelKey", each null, type nullable text),
    HiringRows = Table.SelectColumns(
        HiringChannel,
        {
            "Entity", "WaveKey", "PlanVersionKey", "ApprovalStatus",
            "ValidationStatus", "ProficiencyDate", "ActivityKey", "ChannelKey"
        }
    ),
    HiringRenamed = Table.RenameColumns(
        HiringRows,
        {
            {"WaveKey", "RowKey"}, {"PlanVersionKey", "VersionKey"},
            {"ValidationStatus", "Issue"}, {"ProficiencyDate", "IntervalStart"}
        }
    ),
    Combined = Table.Combine({ForecastRenamed, RequirementRenamed, SupplyRenamed, HiringRenamed}),
    Severity = Table.AddColumn(Combined, "Severity", each "BLOCKING", type text),
    Result = Table.ReorderColumns(
        Severity,
        {
            "Severity", "Entity", "RowKey", "VersionKey", "ApprovalStatus",
            "Issue", "IntervalStart", "ActivityKey", "ChannelKey"
        }
    )
in
    Result
