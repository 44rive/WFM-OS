let
    Config = fxGetSourceConfig("StaffingRequirementSource"),
    Source = src_StaffingRequirements,
    WithSourceActivity = Table.DuplicateColumn(Source, "ActivityExternalID", "SourceActivity"),
    MappedActivity = fxApplyValueMapping(
        WithSourceActivity,
        p_Profile,
        Text.From(Config[SystemKey]),
        "Activity",
        "ActivityExternalID",
        p_AsOfDate,
        "IntervalStart"
    ),
    Renamed = Table.RenameColumns(MappedActivity, {{"ActivityExternalID", "ActivityKey"}}),
    WithBusinessDate = Table.AddColumn(Renamed, "BusinessDate", each Date.From([IntervalStart]), type date),
    WithIntervalKey = Table.AddColumn(
        WithBusinessDate,
        "IntervalKey",
        each "I" & Text.PadStart(
            Text.From(Time.Hour(Time.From([IntervalStart])) * 2 + Number.IntegerDivide(Time.Minute(Time.From([IntervalStart])), 30)),
            2,
            "0"
        ),
        type text
    ),
    WithMappingStatus = Table.AddColumn(
        WithIntervalKey,
        "MappingStatus",
        each
            if [ActivityKey] = null then "UNKNOWN_ACTIVITY"
            else if [RequiredFTE] < 0 then "INVALID_REQUIREMENT"
            else if Time.Minute(Time.From([IntervalStart])) <> 0 and Time.Minute(Time.From([IntervalStart])) <> 30 then "INVALID_INTERVAL_START"
            else "MAPPED",
        type text
    ),
    Result = Table.AddColumn(
        WithMappingStatus,
        "MappingValue",
        each if [ActivityKey] = null then [SystemKey] & "|" & [SourceActivity] else null,
        type nullable text
    )
in
    Result
