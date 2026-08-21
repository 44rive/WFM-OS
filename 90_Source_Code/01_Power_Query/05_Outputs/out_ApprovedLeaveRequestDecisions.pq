let
    Source = fact_LeaveRequestDecision,
    Result = Table.Sort(Source, {{"RequestedStart", Order.Ascending}, {"AgentKey", Order.Ascending}, {"LeaveRequestKey", Order.Ascending}})
in
    Result
