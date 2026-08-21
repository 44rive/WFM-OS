let
    Source = fact_Forecast,
    Result = Table.Sort(
        Source,
        {
            {"BusinessDate", Order.Ascending},
            {"IntervalStart", Order.Ascending},
            {"ActivityKey", Order.Ascending},
            {"ChannelKey", Order.Ascending}
        }
    )
in
    Result
