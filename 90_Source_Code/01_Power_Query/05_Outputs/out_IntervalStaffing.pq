let
    Operational = Table.Combine({fact_OperationalIntervalClosed, fact_OperationalIntervalLive}),
    Staffing = Table.Group(
        Operational,
        {"BusinessDate", "IntervalStart", "IntervalKey", "ActivityKey"},
        {
            {"ScheduledHeads", each List.Count(List.Distinct(Table.SelectRows(_, each [ScheduledSeconds] > 0)[AgentKey])), Int64.Type},
            {"ScheduledProductiveHeads", each List.Count(List.Distinct(Table.SelectRows(_, each [ScheduledProductiveSeconds] > 0)[AgentKey])), Int64.Type},
            {"PresentHeads", each List.Count(List.Distinct(Table.SelectRows(_, each [LoggedScheduledSeconds] > 0)[AgentKey])), Int64.Type},
            {"ProductiveHeads", each List.Count(List.Distinct(Table.SelectRows(_, each [ProductiveActualSeconds] > 0)[AgentKey])), Int64.Type},
            {"ScheduledFTE", each List.Sum([ScheduledSeconds]) / 1800, type number},
            {"ScheduledProductiveFTE", each List.Sum([ScheduledProductiveSeconds]) / 1800, type number},
            {"PresentFTE", each List.Sum([LoggedScheduledSeconds]) / 1800, type number},
            {"ProductiveFTE", each List.Sum([ProductiveActualSeconds]) / 1800, type number},
            {"ScheduledSeconds", each List.Sum([ScheduledSeconds]), type number},
            {"LoggedScheduledSeconds", each List.Sum([LoggedScheduledSeconds]), type number},
            {"AdherentSeconds", each List.Sum([AdherentSeconds]), type number},
            {"ExceptionSeconds", each List.Sum([ExceptionSeconds]), type number}
        }
    ),
    Requirements = Table.Combine({fact_StaffingRequirementClosed, fact_StaffingRequirementLive}),
    Keys = Table.Distinct(
        Table.Combine({
            Table.SelectColumns(Staffing, {"BusinessDate", "IntervalStart", "IntervalKey", "ActivityKey"}),
            Table.SelectColumns(Requirements, {"BusinessDate", "IntervalStart", "IntervalKey", "ActivityKey"})
        })
    ),
    WithStaffing = Table.NestedJoin(
        Keys,
        {"BusinessDate", "IntervalStart", "IntervalKey", "ActivityKey"},
        Staffing,
        {"BusinessDate", "IntervalStart", "IntervalKey", "ActivityKey"},
        "Staffing",
        JoinKind.LeftOuter
    ),
    StaffingColumns = {
        "ScheduledHeads", "ScheduledProductiveHeads", "PresentHeads", "ProductiveHeads",
        "ScheduledFTE", "ScheduledProductiveFTE", "PresentFTE", "ProductiveFTE",
        "ScheduledSeconds", "LoggedScheduledSeconds", "AdherentSeconds", "ExceptionSeconds"
    },
    ExpandedStaffing = Table.ExpandTableColumn(
        WithStaffing,
        "Staffing",
        StaffingColumns,
        StaffingColumns
    ),
    ZeroFilled = Table.ReplaceValue(
        ExpandedStaffing,
        null,
        0,
        Replacer.ReplaceValue,
        StaffingColumns
    ),
    Joined = Table.NestedJoin(
        ZeroFilled,
        {"BusinessDate", "IntervalStart", "ActivityKey"},
        Requirements,
        {"BusinessDate", "IntervalStart", "ActivityKey"},
        "Requirement",
        JoinKind.LeftOuter
    ),
    WithRequirement = Table.AddColumn(
        Joined,
        "RequiredFTE",
        each if Table.RowCount([Requirement]) = 1 then [Requirement]{0}[RequiredFTE] else null,
        type nullable number
    ),
    WithRequirementStatus = Table.AddColumn(
        WithRequirement,
        "RequirementStatus",
        each
            if Table.RowCount([Requirement]) = 0 then "MISSING_REQUIREMENT"
            else if Table.RowCount([Requirement]) > 1 then "AMBIGUOUS_REQUIREMENT"
            else "MAPPED",
        type text
    ),
    WithoutNested = Table.RemoveColumns(WithRequirementStatus, {"Requirement"}),
    WithNet = Table.AddColumn(
        WithoutNested,
        "NetProductiveFTE",
        each if [RequiredFTE] = null then null else [ProductiveFTE] - [RequiredFTE],
        type nullable number
    ),
    WithConformance = Table.AddColumn(
        WithNet,
        "ConformanceRate",
        each if [ScheduledSeconds] = 0 then null else [LoggedScheduledSeconds] / [ScheduledSeconds],
        type nullable number
    ),
    Result = Table.AddColumn(
        WithConformance,
        "AdherenceRate",
        each if [ScheduledSeconds] = 0 then null else [AdherentSeconds] / [ScheduledSeconds],
        type nullable number
    )
in
    Result
