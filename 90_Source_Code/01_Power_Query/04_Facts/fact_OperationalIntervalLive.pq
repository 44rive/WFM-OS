let
    Source = stg_OperationalAgentInterval,
    Filtered = Table.SelectRows(Source, each [BusinessDate] = p_AsOfDate),
    Unique = fxAssertUnique(
        Filtered,
        {"BusinessDate", "IntervalStart", "ActivityKey", "AgentKey"},
        "fact_OperationalIntervalLive"
    )
in
    Unique
