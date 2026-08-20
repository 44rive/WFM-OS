(Input as table, KeyColumns as list, Context as text) as table =>
let
    Duplicates = Table.SelectRows(
        Table.Group(Input, KeyColumns, {{"Rows", each Table.RowCount(_), Int64.Type}}),
        each [Rows] > 1
    ),
    Result =
        if Table.RowCount(Duplicates) = 0 then Input
        else error Error.Record(
            "Duplicate key",
            Context & " contains duplicate canonical keys.",
            [KeyColumns = KeyColumns, DuplicateGroups = Table.RowCount(Duplicates)]
        )
in
    Result
