(SourceRoleName as text) as record =>
let
    RegistrySource = Excel.CurrentWorkbook(){[Name = "tblSourceSystems"]}[Content],
    Registry = fxAssertColumns(
        RegistrySource,
        {
            "Profile", "SystemKey", "SourceRole", "Adapter", "RelativePath",
            "FilePattern", "Format", "Delimiter", "Encoding", "Culture", "Enabled"
        },
        "tblSourceSystems"
    ),
    Active = Table.SelectRows(
        Registry,
        each Text.From([Profile]) = p_Profile
            and Text.From([SourceRole]) = SourceRoleName
            and fxAsLogical([Enabled])
    ),
    Result =
        if Table.RowCount(Active) = 1 then Active{0}
        else error Error.Record(
            "Source configuration",
            "Exactly one enabled source is required for role " & SourceRoleName & ".",
            [Profile = p_Profile, SourceRole = SourceRoleName, EnabledRows = Table.RowCount(Active)]
        )
in
    Result
