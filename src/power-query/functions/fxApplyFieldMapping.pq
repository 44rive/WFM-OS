(Input as table, Profile as text, Entity as text) as table =>
let
    MappingSource = Excel.CurrentWorkbook(){[Name = "tblFieldMapping"]}[Content],
    Mapping = Table.SelectRows(
        MappingSource,
        each [Profile] = Profile and [Entity] = Entity and [Enabled] = true
    ),
    RenamePairs = Table.ToRows(
        Table.SelectColumns(Mapping, {"SourceField", "CanonicalField"})
    ),
    Renamed = Table.RenameColumns(Input, RenamePairs, MissingField.Ignore),
    RequiredFields = Table.Column(
        Table.SelectRows(Mapping, each [Required] = true),
        "CanonicalField"
    ),
    MissingFields = List.Difference(RequiredFields, Table.ColumnNames(Renamed)),
    Result =
        if List.IsEmpty(MissingFields)
        then Renamed
        else error Error.Record(
            "Missing canonical fields",
            Text.Combine(MissingFields, ", "),
            [Profile = Profile, Entity = Entity]
        )
in
    Result
