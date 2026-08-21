let
    ScheduleIssues = Table.SelectRows(stg_Schedules, each [MappingStatus] <> "MAPPED"),
    ScheduleEntity = Table.AddColumn(ScheduleIssues, "Entity", each "ScheduleSegment", type text),
    ScheduleKey = Table.RenameColumns(ScheduleEntity, {{"ScheduleSegmentKey", "SourceKey"}}),
    ScheduleOutput = Table.SelectColumns(
        ScheduleKey,
        {"Entity", "SourceKey", "SystemKey", "MappingStatus", "MappingValue", "SourceFile"}
    ),
    LoginIssues = Table.SelectRows(stg_LoginSessions, each [MappingStatus] <> "MAPPED"),
    LoginEntity = Table.AddColumn(LoginIssues, "Entity", each "LoginSession", type text),
    LoginKey = Table.RenameColumns(LoginEntity, {{"LoginSessionKey", "SourceKey"}}),
    LoginOutput = Table.SelectColumns(
        LoginKey,
        {"Entity", "SourceKey", "SystemKey", "MappingStatus", "MappingValue", "SourceFile"}
    ),
    EventIssues = Table.SelectRows(stg_AgentEvents, each [MappingStatus] <> "MAPPED"),
    EventEntity = Table.AddColumn(EventIssues, "Entity", each "AgentEvent", type text),
    EventKey = Table.RenameColumns(EventEntity, {{"AgentEventKey", "SourceKey"}}),
    EventOutput = Table.SelectColumns(
        EventKey,
        {"Entity", "SourceKey", "SystemKey", "MappingStatus", "MappingValue", "SourceFile"}
    ),
    RequirementIssues = Table.SelectRows(stg_StaffingRequirements, each [MappingStatus] <> "MAPPED"),
    RequirementEntity = Table.AddColumn(RequirementIssues, "Entity", each "StaffingRequirement", type text),
    RequirementKey = Table.RenameColumns(RequirementEntity, {{"RequirementKey", "SourceKey"}}),
    RequirementOutput = Table.SelectColumns(
        RequirementKey,
        {"Entity", "SourceKey", "SystemKey", "MappingStatus", "MappingValue", "SourceFile"}
    ),
    Combined = Table.Combine({ScheduleOutput, LoginOutput, EventOutput, RequirementOutput}),
    Severity = Table.AddColumn(Combined, "Severity", each "BLOCKING", type text),
    Result = Table.ReorderColumns(
        Severity,
        {"Severity", "Entity", "SourceKey", "SystemKey", "MappingStatus", "MappingValue", "SourceFile"}
    )
in
    Result
