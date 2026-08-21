let
    Summarize = (Input as table, EntityName as text) as table =>
        let
            Grouped = Table.Group(
                Input,
                {"BusinessDate", "IntervalStart", "AgentKey"},
                {{"CoveredSeconds", each List.Sum([OverlapSeconds]), type number}}
            ),
            Excess = Table.AddColumn(
                Grouped,
                "ExcessSeconds",
                each List.Max({0, [CoveredSeconds] - 1800}),
                type number
            ),
            Issues = Table.SelectRows(Excess, each [ExcessSeconds] > 0),
            Entity = Table.AddColumn(Issues, "Entity", each EntityName, type text)
        in
            Entity,
    Schedule = Summarize(stg_ScheduleIntervals, "ScheduleSegment"),
    Login = Summarize(stg_LoginIntervals, "LoginSession"),
    Event = Summarize(stg_AgentEventIntervals, "AgentEvent"),
    Combined = Table.Combine({Schedule, Login, Event}),
    Severity = Table.AddColumn(Combined, "Severity", each "BLOCKING", type text),
    Result = Table.ReorderColumns(
        Severity,
        {"Severity", "Entity", "BusinessDate", "IntervalStart", "AgentKey", "CoveredSeconds", "ExcessSeconds"}
    )
in
    Result
