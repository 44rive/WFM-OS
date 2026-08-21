let
    Source = fact_SwapDecision,
    Result = Table.Sort(Source, {{"RosterVersionKey", Order.Ascending}, {"SwapRequestKey", Order.Ascending}})
in
    Result
