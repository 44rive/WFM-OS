let
    Source = stg_OperationalAgentInterval,
    WindowStart = Date.AddMonths(p_AsOfDate, -Number.From(p_HistoryMonths)),
    Filtered = Table.SelectRows(
        Source,
        each [BusinessDate] >= WindowStart and [BusinessDate] < p_AsOfDate
    ),
    Unique = fxAssertUnique(
        Filtered,
        {"BusinessDate", "IntervalStart", "ActivityKey", "AgentKey"},
        "fact_OperationalIntervalClosed"
    )
in
    Unique
