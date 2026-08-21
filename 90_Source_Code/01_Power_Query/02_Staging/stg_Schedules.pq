let
    Config = fxGetSourceConfig("SchedulingTool"),
    Source = src_Schedules,
    WithSourceActivity = Table.DuplicateColumn(Source, "ActivityExternalID", "SourceActivity"),
    WithSourceType = Table.DuplicateColumn(WithSourceActivity, "ScheduleTypeExternalID", "SourceScheduleType"),
    MappedActivity = fxApplyValueMapping(
        WithSourceType,
        p_Profile,
        Text.From(Config[SystemKey]),
        "Activity",
        "ActivityExternalID",
        p_AsOfDate,
        "ScheduledStart"
    ),
    MappedType = fxApplyValueMapping(
        MappedActivity,
        p_Profile,
        Text.From(Config[SystemKey]),
        "ScheduleType",
        "ScheduleTypeExternalID",
        p_AsOfDate,
        "ScheduledStart"
    ),
    Renamed = Table.RenameColumns(
        MappedType,
        {{"ActivityExternalID", "ActivityKey"}, {"ScheduleTypeExternalID", "ScheduleTypeKey"}}
    ),
    Resolved = fxResolveIdentity(Renamed, "AgentExternalID", "ScheduledStart"),
    WithRangeStatus = Table.AddColumn(
        Resolved,
        "RangeStatus",
        each if [ScheduledEnd] > [ScheduledStart] then "VALID" else "INVALID_TIME_RANGE",
        type text
    ),
    WithMappingStatus = Table.AddColumn(
        WithRangeStatus,
        "MappingStatus",
        each
            if [RangeStatus] <> "VALID" then [RangeStatus]
            else if [IdentityStatus] <> "RESOLVED" then [IdentityStatus]
            else if [ActivityKey] = null then "UNKNOWN_ACTIVITY"
            else if [ScheduleTypeKey] = null then "UNKNOWN_SCHEDULE_TYPE"
            else "MAPPED",
        type text
    ),
    Result = Table.AddColumn(
        WithMappingStatus,
        "MappingValue",
        each
            if [IdentityStatus] <> "RESOLVED" then [IdentityValue]
            else if [ActivityKey] = null then [SystemKey] & "|" & [SourceActivity]
            else if [ScheduleTypeKey] = null then [SystemKey] & "|" & [SourceScheduleType]
            else null,
        type nullable text
    )
in
    Result
