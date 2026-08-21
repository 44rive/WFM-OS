let
    Source = fact_PublishedRosterSegment,
    Result = Table.Sort(Source, {{"IntervalStart", Order.Ascending}, {"AgentKey", Order.Ascending}, {"SegmentKey", Order.Ascending}})
in
    Result
