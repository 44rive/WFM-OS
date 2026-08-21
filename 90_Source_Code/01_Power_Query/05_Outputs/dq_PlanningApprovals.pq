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
    ScheduleIssues = Table.SelectRows(
        stg_SchedulePlanVersions,
        each [ApprovedFlag] and [ValidationStatus] <> "VALID"
    ),
    ScheduleEntity = Table.AddColumn(ScheduleIssues, "Entity", each "SchedulePlan", type text),
    ScheduleChannel = Table.AddColumn(ScheduleEntity, "ChannelKey", each null, type nullable text),
    ScheduleRows = Table.SelectColumns(
        ScheduleChannel,
        {
            "Entity", "SchedulePlanRowKey", "SchedulePlanVersionKey", "ApprovalStatus",
            "ValidationStatus", "BusinessDate", "ActivityKey", "ChannelKey"
        }
    ),
    ScheduleRenamed = Table.RenameColumns(
        ScheduleRows,
        {
            {"SchedulePlanRowKey", "RowKey"}, {"SchedulePlanVersionKey", "VersionKey"},
            {"ValidationStatus", "Issue"}, {"BusinessDate", "IntervalStart"}
        }
    ),
    LeaveIssues = Table.SelectRows(
        stg_LeavePlanVersions,
        each [ApprovedFlag] and [ValidationStatus] <> "VALID"
    ),
    LeaveEntity = Table.AddColumn(LeaveIssues, "Entity", each "LeavePlan", type text),
    LeaveChannel = Table.AddColumn(LeaveEntity, "ChannelKey", each null, type nullable text),
    LeaveRows = Table.SelectColumns(
        LeaveChannel,
        {
            "Entity", "LeavePlanRowKey", "LeavePlanVersionKey", "ApprovalStatus",
            "ValidationStatus", "IntervalStart", "ActivityKey", "ChannelKey"
        }
    ),
    LeaveRenamed = Table.RenameColumns(
        LeaveRows,
        {
            {"LeavePlanRowKey", "RowKey"}, {"LeavePlanVersionKey", "VersionKey"},
            {"ValidationStatus", "Issue"}
        }
    ),
    Undercovered = Table.SelectRows(fact_ScheduleCoverage, each [CoverageStatus] = "UNCOVERED"),
    UndercoveredWithEntity = Table.AddColumn(Undercovered, "Entity", each "ScheduleCoverage", type text),
    UndercoveredWithRowKey = Table.AddColumn(
        UndercoveredWithEntity,
        "RowKey",
        each Text.Combine(
            {[SchedulePlanVersionKey], [ScenarioKey], DateTime.ToText([IntervalStart], "yyyyMMddHHmm"), [ActivityKey]},
            "|"
        ),
        type text
    ),
    UndercoveredWithApproval = Table.AddColumn(UndercoveredWithRowKey, "ApprovalStatus", each "APPROVED", type text),
    UndercoveredWithIssue = Table.AddColumn(UndercoveredWithApproval, "Issue", each "APPROVED_SCHEDULE_UNDERCOVERED", type text),
    UndercoveredWithChannel = Table.AddColumn(UndercoveredWithIssue, "ChannelKey", each null, type nullable text),
    UndercoveredRows = Table.SelectColumns(
        UndercoveredWithChannel,
        {"Entity", "RowKey", "SchedulePlanVersionKey", "ApprovalStatus", "Issue", "IntervalStart", "ActivityKey", "ChannelKey"}
    ),
    UndercoveredRenamed = Table.RenameColumns(UndercoveredRows, {{"SchedulePlanVersionKey", "VersionKey"}}),
    Combined = Table.Combine(
        {
            ForecastRenamed, RequirementRenamed, SupplyRenamed, HiringRenamed,
            ScheduleRenamed, LeaveRenamed, UndercoveredRenamed
        }
    ),
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
