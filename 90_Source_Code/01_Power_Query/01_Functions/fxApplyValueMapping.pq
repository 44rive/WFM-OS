(Input as table, ProfileName as text, SystemName as text, DomainName as text, ColumnName as text, EffectiveDate as date) as table =>
let
    MappingSource = Excel.CurrentWorkbook(){[Name = "tblValueMapping"]}[Content],
    RequiredMapping = fxAssertColumns(
        MappingSource,
        {"Profile", "SystemKey", "Domain", "SourceValue", "CanonicalValue", "ValidFrom", "ValidTo", "Enabled"},
        "tblValueMapping"
    ),
    Typed = Table.TransformColumnTypes(
        RequiredMapping,
        {
            {"Profile", type text}, {"SystemKey", type text}, {"Domain", type text},
            {"SourceValue", type text}, {"CanonicalValue", type text},
            {"ValidFrom", type date}, {"ValidTo", type nullable date}
        }
    ),
    Mapping = Table.SelectRows(
        Typed,
        each [Profile] = ProfileName
            and [SystemKey] = SystemName
            and [Domain] = DomainName
            and fxAsLogical([Enabled])
            and [ValidFrom] <= EffectiveDate
            and ([ValidTo] = null or [ValidTo] >= EffectiveDate)
    ),
    DuplicateCheck = Table.SelectRows(
        Table.Group(Mapping, {"SourceValue"}, {{"Rows", each Table.RowCount(_), Int64.Type}}),
        each [Rows] > 1
    ),
    MappingRecord = Record.FromList(
        Mapping[CanonicalValue],
        Mapping[SourceValue]
    ),
    Mapped =
        if Table.RowCount(DuplicateCheck) > 0 then
            error Error.Record(
                "Duplicate value mapping",
                DomainName & " has overlapping mappings for the same source value.",
                [Profile = ProfileName, SystemKey = SystemName]
            )
        else Table.TransformColumns(
            Input,
            {{
                ColumnName,
                each Record.FieldOrDefault(MappingRecord, Text.From(_), null),
                type nullable text
            }}
        )
in
    Mapped
