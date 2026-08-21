(Input as table, ExternalIdentityColumn as text, ObservedAtColumn as text) as table =>
let
    MappingSource = Excel.CurrentWorkbook(){[Name = "tblIdentityMapping"]}[Content],
    Contract = fxAssertColumns(
        MappingSource,
        {"Profile", "SystemKey", "ExternalAgentID", "AgentKey", "ValidFrom", "ValidTo", "Enabled"},
        "tblIdentityMapping"
    ),
    Typed = Table.TransformColumnTypes(
        Contract,
        {
            {"Profile", type text}, {"SystemKey", type text},
            {"ExternalAgentID", type text}, {"AgentKey", type text},
            {"ValidFrom", type date}, {"ValidTo", type nullable date}
        }
    ),
    Active = Table.SelectRows(
        Typed,
        each [Profile] = p_Profile and fxAsLogical([Enabled])
    ),
    WithMatches = Table.AddColumn(
        Input,
        "IdentityMatches",
        (Current as record) as table =>
            let
                SystemValue = Text.From(Record.Field(Current, "SystemKey")),
                IdentityValue = Text.From(Record.Field(Current, ExternalIdentityColumn)),
                ObservedDate = Date.From(Record.Field(Current, ObservedAtColumn))
            in
                Table.SelectRows(
                    Active,
                    each [SystemKey] = SystemValue
                        and [ExternalAgentID] = IdentityValue
                        and [ValidFrom] <= ObservedDate
                        and ([ValidTo] = null or [ValidTo] >= ObservedDate)
                ),
        type table
    ),
    WithCount = Table.AddColumn(
        WithMatches,
        "IdentityMatchCount",
        each Table.RowCount([IdentityMatches]),
        Int64.Type
    ),
    WithAgent = Table.AddColumn(
        WithCount,
        "AgentKey",
        each if [IdentityMatchCount] = 1 then [IdentityMatches]{0}[AgentKey] else null,
        type nullable text
    ),
    WithStatus = Table.AddColumn(
        WithAgent,
        "IdentityStatus",
        each
            if [IdentityMatchCount] = 0 then "UNKNOWN_IDENTITY"
            else if [IdentityMatchCount] > 1 then "AMBIGUOUS_IDENTITY"
            else "RESOLVED",
        type text
    ),
    WithValue = Table.AddColumn(
        WithStatus,
        "IdentityValue",
        each [SystemKey] & "|" & Text.From(Record.Field(_, ExternalIdentityColumn)),
        type text
    ),
    Result = Table.RemoveColumns(WithValue, {"IdentityMatches"})
in
    Result
