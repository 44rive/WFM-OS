let
    Source = fact_ScheduleCoverage,
    Result = Table.Sort(
        Source,
        {
            {"BusinessDate", Order.Ascending}, {"IntervalStart", Order.Ascending},
            {"ScenarioKey", Order.Ascending}, {"ActivityKey", Order.Ascending}
        }
    )
in
    Result
