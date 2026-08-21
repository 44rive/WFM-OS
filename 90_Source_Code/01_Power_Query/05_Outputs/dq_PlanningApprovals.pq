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
    RequirementChannel = Table.AddColumn(RequirementEntity, "ChannelKey", each null, type nullable text),
    RequirementRows = Table.SelectColumns(
        RequirementChannel,
        {
            "Entity", "RequirementKey", "RequirementVersion", "ApprovalStatus",
            "MappingStatus", "IntervalStart", "ActivityKey", "ChannelKey"
        }
    ),
    RequirementRenamed = Table.RenameColumns(
        RequirementRows,
        {{"RequirementKey", "RowKey"}, {"RequirementVersion", "VersionKey"}, {"MappingStatus", "Issue"}}
    ),
    Combined = Table.Combine({ForecastRenamed, RequirementRenamed}),
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
