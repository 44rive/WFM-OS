(Input as table, RequiredColumns as list, Context as text) as table =>
let
    Missing = List.Difference(RequiredColumns, Table.ColumnNames(Input)),
    Result =
        if List.IsEmpty(Missing) then Input
        else error Error.Record(
            "Schema contract failed",
            Context & " is missing required columns: " & Text.Combine(Missing, ", "),
            [Context = Context, MissingColumns = Missing]
        )
in
    Result
