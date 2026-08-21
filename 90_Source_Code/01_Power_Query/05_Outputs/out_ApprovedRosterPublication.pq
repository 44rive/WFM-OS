let
    Source = fact_RosterPublication,
    Result = Table.Sort(Source, {{"StartDate", Order.Ascending}, {"PublicationVersionKey", Order.Ascending}})
in
    Result
