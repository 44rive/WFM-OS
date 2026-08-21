(Input as table, ExternalStateColumn as text, ObservedAtColumn as text) as table =>
let
    MappingSource = Excel.CurrentWorkbook(){[Name = "tblStateMapping"]}[Content],
    Contract = fxAssertColumns(
        MappingSource,
        {
            "Profile", "SystemKey", "SourceStateID", "StateKey", "StateName",
            "AdherenceClass", "PresentFlag", "ProductiveFlag", "ValidFrom", "ValidTo", "Enabled"
        },
        "tblStateMapping"
    ),
    Typed = Table.TransformColumnTypes(
        Contract,
        {
            {"Profile", type text}, {"SystemKey", type text},
            {"SourceStateID", type text}, {"StateKey", type text},
            {"ValidFrom", type date}, {"ValidTo", type nullable date}
        }
    ),
    Active = Table.SelectRows(
        Typed,
        each [Profile] = p_Profile and fxAsLogical([Enabled])
    ),
    WithMatches = Table.AddColumn(
        Input,
        "StateMatches",
        (Current as record) as table =>
            let
                SystemValue = Text.From(Record.Field(Current, "SystemKey")),
                StateValue = Text.From(Record.Field(Current, ExternalStateColumn)),
                ObservedDate = Date.From(Record.Field(Current, ObservedAtColumn))
            in
                Table.SelectRows(
                    Active,
                    each [SystemKey] = SystemValue
                        and [SourceStateID] = StateValue
                        and [ValidFrom] <= ObservedDate
                        and ([ValidTo] = null or [ValidTo] >= ObservedDate)
                ),
        type table
    ),
    WithCount = Table.AddColumn(WithMatches, "StateMatchCount", each Table.RowCount([StateMatches]), Int64.Type),
    WithRecord = Table.AddColumn(
        WithCount,
        "StateMapping",
        each if [StateMatchCount] = 1 then [StateMatches]{0} else null,
        type nullable record
    ),
    WithoutMatches = Table.RemoveColumns(WithRecord, {"StateMatches"}),
    Expanded = Table.ExpandRecordColumn(
        WithoutMatches,
        "StateMapping",
        {"StateKey", "StateName", "AdherenceClass", "PresentFlag", "ProductiveFlag"},
        {"StateKey", "StateName", "AdherenceClass", "StatePresentFlag", "StateProductiveFlag"}
    ),
    WithStatus = Table.AddColumn(
        Expanded,
        "StateStatus",
        each
            if [StateMatchCount] = 0 then "UNKNOWN_STATE"
            else if [StateMatchCount] > 1 then "AMBIGUOUS_STATE"
            else "RESOLVED",
        type text
    ),
    Result = Table.AddColumn(
        WithStatus,
        "StateValue",
        each [SystemKey] & "|" & Text.From(Record.Field(_, ExternalStateColumn)),
        type text
    )
in
    Result
