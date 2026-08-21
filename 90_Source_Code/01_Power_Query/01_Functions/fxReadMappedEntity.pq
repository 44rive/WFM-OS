(SourceRoleName as text, EntityName as text) as table =>
let
    Config = fxGetSourceConfig(SourceRoleName),
    FormatCheck =
        if Text.Lower(Text.From(Config[Format])) = "csv" then Config
        else error Error.Record(
            "Unsupported source format",
            "The generic operational adapter currently accepts CSV extracts only.",
            [SourceRole = SourceRoleName, Format = Config[Format]]
        ),
    FolderPath = fxCombinePath(p_RootPath, Text.From(FormatCheck[RelativePath])),
    Raw = fxReadDelimitedFolder(
        FolderPath,
        Text.From(FormatCheck[FilePattern]),
        Text.From(FormatCheck[Delimiter]),
        Number.From(FormatCheck[Encoding])
    ),
    Mapped = fxApplyFieldMapping(
        Raw,
        p_Profile,
        Text.From(FormatCheck[Adapter]),
        EntityName
    ),
    WithSystem = Table.AddColumn(
        Mapped,
        "SystemKey",
        each Text.From(FormatCheck[SystemKey]),
        type text
    ),
    WithCulture = Table.AddColumn(
        WithSystem,
        "SourceCulture",
        each Text.From(FormatCheck[Culture]),
        type text
    )
in
    WithCulture
