(ParameterName as text, optional DefaultValue as any) as any =>
let
    Source = Excel.CurrentWorkbook(){[Name = "tblParameters"]}[Content],
    Required = fxAssertColumns(
        Source,
        {"Parameter", "Value", "DataType"},
        "tblParameters"
    ),
    Match = Table.SelectRows(
        Required,
        each Text.Trim(Text.From([Parameter])) = ParameterName
    ),
    RawValue =
        if Table.RowCount(Match) = 1 then Match{0}[Value]
        else if Table.RowCount(Match) = 0 and DefaultValue <> null then DefaultValue
        else if Table.RowCount(Match) = 0 then
            error Error.Record(
                "Missing parameter",
                ParameterName & " is required in tblParameters.",
                [Parameter = ParameterName]
            )
        else
            error Error.Record(
                "Duplicate parameter",
                ParameterName & " must appear exactly once in tblParameters.",
                [Parameter = ParameterName, Rows = Table.RowCount(Match)]
            ),
    DataType =
        if Table.RowCount(Match) = 1
        then Text.Lower(Text.Trim(Text.From(Match{0}[DataType])))
        else null,
    Converted =
        if DataType = "date" then Date.From(RawValue)
        else if DataType = "datetime" then DateTime.From(RawValue)
        else if DataType = "number" then Number.From(RawValue)
        else if DataType = "logical" or DataType = "boolean" then fxAsLogical(RawValue)
        else if RawValue = null then null
        else Text.From(RawValue)
in
    Converted
