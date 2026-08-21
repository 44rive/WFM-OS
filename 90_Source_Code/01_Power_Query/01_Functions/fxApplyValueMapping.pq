(Input as table, ProfileName as text, SystemName as text, DomainName as text, ColumnName as text, EffectiveDate as date, optional EffectiveDateColumn as nullable text) as table =>
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
    BaseMapping = Table.SelectRows(
        Typed,
        each [Profile] = ProfileName
            and [SystemKey] = SystemName
            and [Domain] = DomainName
            and fxAsLogical([Enabled])
    ),
    StaticMapping = Table.SelectRows(
        BaseMapping,
        each [ValidFrom] <= EffectiveDate
            and ([ValidTo] = null or [ValidTo] >= EffectiveDate)
    ),
    StaticDuplicateCheck = Table.SelectRows(
        Table.Group(StaticMapping, {"SourceValue"}, {{"Rows", each Table.RowCount(_), Int64.Type}}),
        each [Rows] > 1
    ),
    MappingRecord = Record.FromList(
        StaticMapping[CanonicalValue],
        StaticMapping[SourceValue]
    ),
    StaticMapped =
        if Table.RowCount(StaticDuplicateCheck) > 0 then
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
        ),
    WithTemporalValue = Table.AddColumn(
        Input,
        "__MappedValue",
        (Current as record) as nullable text =>
            let
                RowDate = Date.From(Record.Field(Current, EffectiveDateColumn)),
                SourceText = Text.From(Record.Field(Current, ColumnName)),
                Matches = Table.SelectRows(
                    BaseMapping,
                    each [SourceValue] = SourceText
                        and [ValidFrom] <= RowDate
                        and ([ValidTo] = null or [ValidTo] >= RowDate)
                ),
                Result =
                    if Table.RowCount(Matches) = 0 then null
                    else if Table.RowCount(Matches) = 1 then Matches{0}[CanonicalValue]
                    else error Error.Record(
                        "Duplicate value mapping",
                        DomainName & " has overlapping mappings for " & SourceText & ".",
                        [Profile = ProfileName, SystemKey = SystemName, EffectiveDate = RowDate]
                    )
            in
                Result,
        type nullable text
    ),
    WithoutSourceValue = Table.RemoveColumns(WithTemporalValue, {ColumnName}),
    TemporalMapped = Table.RenameColumns(WithoutSourceValue, {{"__MappedValue", ColumnName}}),
    Mapped = if EffectiveDateColumn = null then StaticMapped else TemporalMapped
in
    Mapped
