(Input as table, ProfileName as text, AdapterName as text, EntityName as text) as table =>
let
    MappingSource = Excel.CurrentWorkbook(){[Name = "tblFieldMapping"]}[Content],
    RequiredMapping = fxAssertColumns(
        MappingSource,
        {"Profile", "Adapter", "Entity", "SourceField", "CanonicalField", "Required", "Enabled"},
        "tblFieldMapping"
    ),
    Mapping = Table.SelectRows(
        RequiredMapping,
        each Text.From([Profile]) = ProfileName
            and Text.From([Adapter]) = AdapterName
            and Text.From([Entity]) = EntityName
            and fxAsLogical([Enabled])
    ),
    RenamePairs = Table.ToRows(
        Table.SelectColumns(Mapping, {"SourceField", "CanonicalField"})
    ),
    Renamed = Table.RenameColumns(Input, RenamePairs, MissingField.Ignore),
    RequiredFields = Table.Column(
        Table.SelectRows(Mapping, each fxAsLogical([Required])),
        "CanonicalField"
    ),
    MissingFields = List.Difference(RequiredFields, Table.ColumnNames(Renamed)),
    Result =
        if List.IsEmpty(MissingFields)
        then Renamed
        else error Error.Record(
            "Missing canonical fields",
            Text.Combine(MissingFields, ", "),
            [Profile = ProfileName, Adapter = AdapterName, Entity = EntityName]
        )
in
    Result
