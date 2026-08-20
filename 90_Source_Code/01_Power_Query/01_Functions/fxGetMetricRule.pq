(ProfileName as text, MetricName as text, RuleName as text, EffectiveDate as date, optional DefaultValue as any) as any =>
let
    Source = Excel.CurrentWorkbook(){[Name = "tblMetricRules"]}[Content],
    Required = fxAssertColumns(
        Source,
        {"Profile", "MetricKey", "RuleName", "Value", "ValidFrom", "ValidTo", "Approved"},
        "tblMetricRules"
    ),
    Typed = Table.TransformColumnTypes(
        Required,
        {{"ValidFrom", type date}, {"ValidTo", type nullable date}}
    ),
    Match = Table.SelectRows(
        Typed,
        each Text.From([Profile]) = ProfileName
            and Text.From([MetricKey]) = MetricName
            and Text.From([RuleName]) = RuleName
            and fxAsLogical([Approved])
            and [ValidFrom] <= EffectiveDate
            and ([ValidTo] = null or [ValidTo] >= EffectiveDate)
    ),
    Result =
        if Table.RowCount(Match) = 1 then Match{0}[Value]
        else if Table.RowCount(Match) = 0 and DefaultValue <> null then DefaultValue
        else if Table.RowCount(Match) = 0 then
            error Error.Record(
                "Missing approved metric rule",
                MetricName & "/" & RuleName & " has no active approved value.",
                [Profile = ProfileName, EffectiveDate = EffectiveDate]
            )
        else
            error Error.Record(
                "Overlapping metric rules",
                MetricName & "/" & RuleName & " has multiple active approved values.",
                [Profile = ProfileName, EffectiveDate = EffectiveDate]
            )
in
    Result
