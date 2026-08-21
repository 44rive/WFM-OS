let
    Source = fact_RosterPlan,
    Result = Table.Sort(Source, {{"BusinessDate", Order.Ascending}, {"ActivityKey", Order.Ascending}, {"OccurrenceKey", Order.Ascending}})
in
    Result
