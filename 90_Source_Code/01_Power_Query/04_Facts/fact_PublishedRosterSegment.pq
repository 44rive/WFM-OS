let
    Publications = fact_RosterPublication,
    Rosters = fact_RosterPlan,
    PublicationRoster = Table.NestedJoin(Publications, {"RosterVersionKey"}, Rosters, {"RosterVersionKey"}, "RosterRows", JoinKind.Inner),
    ExpandedRoster = Table.ExpandTableColumn(
        PublicationRoster,
        "RosterRows",
        {
            "AssignmentKey", "OccurrenceKey", "BusinessDate", "ActivityKey", "PatternVersionKey",
            "PatternKey", "OccurrenceOrdinal", "AgentKey", "PaidHours", "ProductiveHours"
        },
        {
            "AssignmentKey", "OccurrenceKey", "BusinessDate", "ActivityKey", "PatternVersionKey",
            "PatternKey", "OccurrenceOrdinal", "AgentKey", "PaidHours", "ProductiveHours"
        }
    ),
    InHorizon = Table.SelectRows(ExpandedRoster, each [BusinessDate] >= [StartDate] and [BusinessDate] <= [EndDate]),
    ApprovedSwaps = Table.SelectRows(fact_SwapDecision, each [RecommendationStatus] = "APPROVE"),
    WithSwap = Table.AddColumn(
        InHorizon,
        "EffectiveAgentKey",
        each let
            Assignment = [AssignmentKey],
            CurrentRoster = [RosterVersionKey],
            Version = [SwapDecisionVersionKey],
            Matches =
                if Version = null or Version = "" then Table.FirstN(ApprovedSwaps, 0)
                else Table.SelectRows(
                    ApprovedSwaps,
                    (SwapRow) =>
                        SwapRow[RosterVersionKey] = CurrentRoster
                            and SwapRow[SwapDecisionVersionKey] = Version
                            and (SwapRow[AssignmentKeyA] = Assignment or SwapRow[AssignmentKeyB] = Assignment)
                )
        in
            if Table.RowCount(Matches) = 0 then [AgentKey]
            else if Table.RowCount(Matches) = 1 and Matches{0}[AssignmentKeyA] = Assignment then Matches{0}[AgentKeyB]
            else if Table.RowCount(Matches) = 1 then Matches{0}[AgentKeyA]
            else error "Multiple approved swaps affect one assignment",
        type text
    ),
    PatternSource = Excel.CurrentWorkbook(){[Name = "tblShiftPatterns"]}[Content],
    PatternContract = fxAssertColumns(
        PatternSource,
        {
            "Profile", "PatternVersionKey", "PatternKey", "PatternName", "ActivityKey",
            "DayType", "SegmentKey", "StartMinute", "EndMinute", "ScheduleTypeKey",
            "PaidFlag", "ProductiveFlag", "ValidFrom", "ValidTo", "Approved"
        },
        "tblShiftPatterns"
    ),
    PatternTyped = Table.TransformColumnTypes(
        PatternContract,
        {
            {"Profile", type text}, {"PatternVersionKey", type text}, {"PatternKey", type text},
            {"ActivityKey", type text}, {"DayType", type text}, {"SegmentKey", type text},
            {"StartMinute", Int64.Type}, {"EndMinute", Int64.Type}, {"ScheduleTypeKey", type text},
            {"ValidFrom", type date}, {"ValidTo", type nullable date}
        }
    ),
    Patterns = Table.SelectRows(
        Table.TransformColumns(
            PatternTyped,
            {
                {"Approved", each fxAsLogical(_), type logical},
                {"PaidFlag", each fxAsLogical(_), type logical},
                {"ProductiveFlag", each fxAsLogical(_), type logical},
                {"DayType", each Text.Upper(Text.Trim(Text.From(_))), type text}
            }
        ),
        each [Profile] = p_Profile and [Approved]
    ),
    WithSegments = Table.AddColumn(
        WithSwap,
        "PatternSegments",
        each let
            CurrentDate = [BusinessDate],
            CurrentActivity = [ActivityKey],
            CurrentVersion = [PatternVersionKey],
            CurrentPattern = [PatternKey],
            Weekday = Text.Upper(Date.DayOfWeekName(CurrentDate, "en-US")),
            Effective = Table.SelectRows(
                Patterns,
                (PatternRow) =>
                    PatternRow[ActivityKey] = CurrentActivity
                        and PatternRow[PatternVersionKey] = CurrentVersion
                        and PatternRow[PatternKey] = CurrentPattern
                        and PatternRow[ValidFrom] <= CurrentDate
                        and (PatternRow[ValidTo] = null or PatternRow[ValidTo] >= CurrentDate)
                        and List.Contains({"ALL", Weekday}, PatternRow[DayType])
            ),
            Exact = Table.SelectRows(Effective, each [DayType] = Weekday)
        in
            if Table.IsEmpty(Exact) then Table.SelectRows(Effective, each [DayType] = "ALL") else Exact,
        type table
    ),
    ExpandedSegments = Table.ExpandTableColumn(
        WithSegments,
        "PatternSegments",
        {"SegmentKey", "StartMinute", "EndMinute", "ScheduleTypeKey", "PaidFlag", "ProductiveFlag"},
        {"PatternSegmentKey", "StartMinute", "EndMinute", "ScheduleTypeKey", "PaidFlag", "ProductiveFlag"}
    ),
    WithOffsets = Table.AddColumn(
        ExpandedSegments,
        "OffsetMinute",
        each List.Numbers([StartMinute], Number.IntegerDivide([EndMinute] - [StartMinute], 30), 30),
        type list
    ),
    ExpandedOffsets = Table.ExpandListColumn(WithOffsets, "OffsetMinute"),
    WithIntervalStart = Table.AddColumn(
        ExpandedOffsets,
        "IntervalStart",
        each DateTime.From([BusinessDate]) + #duration(0, 0, [OffsetMinute], 0),
        type datetime
    ),
    ApprovedLeave = Table.SelectRows(fact_LeaveRequestDecision, each [RecommendationStatus] = "APPROVE"),
    WithLeave = Table.AddColumn(
        WithIntervalStart,
        "OnApprovedLeave",
        each let
            CurrentAgent = [EffectiveAgentKey],
            CurrentInterval = [IntervalStart],
            CurrentRoster = [RosterVersionKey],
            CurrentLeaveVersion = [LeaveDecisionVersionKey],
            CurrentSwapVersion = [SwapDecisionVersionKey]
            Matches =
                if CurrentLeaveVersion = null or CurrentLeaveVersion = "" then Table.FirstN(ApprovedLeave, 0)
                else Table.SelectRows(
                    ApprovedLeave,
                    (LeaveRow) =>
                        LeaveRow[RosterVersionKey] = CurrentRoster
                            and LeaveRow[LeaveDecisionVersionKey] = CurrentLeaveVersion
                            and (CurrentSwapVersion = null or CurrentSwapVersion = "" or LeaveRow[SwapDecisionVersionKey] = CurrentSwapVersion)
                            and LeaveRow[AgentKey] = CurrentAgent
                            and LeaveRow[RequestedStart] <= CurrentInterval
                            and LeaveRow[RequestedEnd] > CurrentInterval
                )
        in
            if Table.RowCount(Matches) <= 1 then Table.RowCount(Matches) = 1
            else error "Multiple approved leave decisions affect one published agent interval",
        type logical
    ),
    WithEffectiveType = Table.AddColumn(WithLeave, "EffectiveScheduleTypeKey", each if [OnApprovedLeave] and [PaidFlag] then "LEAVE" else [ScheduleTypeKey], type text),
    WithEffectiveProductive = Table.AddColumn(WithEffectiveType, "EffectiveProductiveFlag", each [ProductiveFlag] and not [OnApprovedLeave], type logical),
    WithIntervalKey = Table.AddColumn(WithEffectiveProductive, "IntervalKey", each "I" & Text.PadStart(Text.From(Time.Hour(Time.From([IntervalStart])) * 2 + Number.IntegerDivide(Time.Minute(Time.From([IntervalStart])), 30)), 2, "0"), type text),
    WithSegmentKey = Table.AddColumn(WithIntervalKey, "PublishedSegmentKey", each Text.Combine({[OccurrenceKey], [PatternSegmentKey], DateTime.ToText([IntervalStart], "yyyyMMddHHmm")}, "|"), type text),
    WithStatus = Table.AddColumn(WithSegmentKey, "PublicationStatus", each "PUBLISHED", type text),
    WithSeconds = Table.AddColumn(WithStatus, "ScheduledSeconds", each if [PaidFlag] then 1800 else 0, Int64.Type),
    Selected = Table.SelectColumns(
        WithSeconds,
        {
            "PublicationVersionKey", "RosterVersionKey", "OccurrenceKey", "PublishedSegmentKey",
            "BusinessDate", "IntervalStart", "IntervalKey", "EffectiveAgentKey", "ActivityKey",
            "EffectiveScheduleTypeKey", "PaidFlag", "EffectiveProductiveFlag", "ScheduledSeconds", "PublicationStatus"
        }
    ),
    Renamed = Table.RenameColumns(
        Selected,
        {
            {"PublishedSegmentKey", "SegmentKey"}, {"EffectiveAgentKey", "AgentKey"},
            {"EffectiveScheduleTypeKey", "ScheduleTypeKey"}, {"EffectiveProductiveFlag", "ProductiveFlag"}
        }
    ),
    Unique = fxAssertUnique(Renamed, {"PublicationVersionKey", "SegmentKey"}, "fact_PublishedRosterSegment")
in
    Unique
