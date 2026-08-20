let
    Parameters = Excel.CurrentWorkbook(){[Name = "tblParameters"]}[Content],
    Typed = Table.TransformColumnTypes(
        Parameters,
        {{"Parameter", type text}, {"Value", type text}}
    ),
    Match = Table.SelectRows(Typed, each [Parameter] = "RootPath"),
    RootPath =
        if Table.RowCount(Match) = 1
        then Text.Trim(Match{0}[Value])
        else error "Parameter RootPath must exist exactly once in tblParameters."
in
    RootPath
