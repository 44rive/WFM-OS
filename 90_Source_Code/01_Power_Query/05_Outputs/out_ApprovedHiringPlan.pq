let
    Source = fact_HiringPlan,
    Result = Table.Sort(
        Source,
        {{"ProficiencyDate", Order.Ascending}, {"ScenarioKey", Order.Ascending}, {"ActivityKey", Order.Ascending}}
    )
in
    Result
