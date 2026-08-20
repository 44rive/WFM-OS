(Input as table, Profile as text, Domain as text, ColumnName as text) as table =>
let
    MappingSource = Excel.CurrentWorkbook(){[Name = "tblValueMapping"]}[Content],
    Mapping = Table.SelectRows(
        MappingSource,
        each [Profile] = Profile and [Domain] = Domain and [Enabled] = true
    ),
    MappingRecord = Record.FromList(
        Mapping[CanonicalValue],
        Mapping[SourceValue]
    ),
    Mapped = Table.TransformColumns(
        Input,
        {{
            ColumnName,
            each Record.FieldOrDefault(MappingRecord, Text.From(_), null),
            type nullable text
        }}
    )
in
    Mapped
