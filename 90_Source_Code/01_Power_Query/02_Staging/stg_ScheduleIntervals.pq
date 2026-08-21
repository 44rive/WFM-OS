let
    Source = Table.SelectRows(stg_Schedules, each [MappingStatus] = "MAPPED"),
    Unique = fxAssertUnique(Source, {"ScheduleSegmentKey"}, "stg_Schedules"),
    Expanded = fxExpandIntervals(Unique, "ScheduledStart", "ScheduledEnd", 30),
    WithScheduled = Table.AddColumn(
        Expanded,
        "ScheduledSeconds",
        each if [PaidFlag] then [OverlapSeconds] else 0,
        type number
    ),
    Result = Table.AddColumn(
        WithScheduled,
        "ScheduledProductiveSeconds",
        each if [PaidFlag] and [ProductiveFlag] then [OverlapSeconds] else 0,
        type number
    )
in
    Result
