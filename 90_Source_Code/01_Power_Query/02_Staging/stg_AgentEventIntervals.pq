let
    Source = Table.SelectRows(stg_AgentEvents, each [MappingStatus] = "MAPPED"),
    Unique = fxAssertUnique(Source, {"AgentEventKey"}, "stg_AgentEvents"),
    Result = fxExpandIntervals(Unique, "EventStart", "EventEnd", 30)
in
    Result
