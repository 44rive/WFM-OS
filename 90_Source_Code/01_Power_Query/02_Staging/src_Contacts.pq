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
            and Text.From([SourceRole]) = "ContactPlatform"
            and fxAsLogical([Enabled])
    ),
    Config =
        if Table.RowCount(Active) = 1 then Active{0}
        else error Error.Record(
            "Contact source configuration",
            "Exactly one enabled ContactPlatform source is required for the active profile.",
            [Profile = p_Profile, EnabledRows = Table.RowCount(Active)]
        ),
    FormatCheck =
        if Text.Lower(Text.From(Config[Format])) = "csv" then Config
        else error "The first vertical slice supports delimited CSV contact sources only.",
    FolderPath = fxCombinePath(p_RootPath, Text.From(FormatCheck[RelativePath])),
    Raw = fxReadDelimitedFolder(
        FolderPath,
        Text.From(FormatCheck[FilePattern]),
        Text.From(FormatCheck[Delimiter]),
        Number.From(FormatCheck[Encoding])
    ),
    Renamed = fxApplyFieldMapping(
        Raw,
        p_Profile,
        Text.From(FormatCheck[Adapter]),
        "Contact"
    ),
    Contract = fxAssertColumns(
        Renamed,
        {
            "SourceContactID", "ContactStart", "ChannelExternalID",
            "QueueExternalID", "Direction", "Outcome", "WaitSeconds"
        },
        "Contact adapter output"
    ),
    OptionalColumns = List.Accumulate(
        {
            {"ContactEnd", type nullable datetime},
            {"AgentExternalID", type nullable text},
            {"TalkSeconds", type nullable number},
            {"HoldSeconds", type nullable number},
            {"AfterContactSeconds", type nullable number}
        },
        Contract,
        (State as table, Definition as list) as table =>
            if List.Contains(Table.ColumnNames(State), Definition{0}) then State
            else Table.AddColumn(State, Definition{0}, each null, Definition{1})
    ),
    TypedCore = Table.TransformColumnTypes(
        OptionalColumns,
        {
            {"SourceContactID", type text},
            {"ContactStart", type datetime},
            {"ContactEnd", type nullable datetime},
            {"ChannelExternalID", type text},
            {"QueueExternalID", type text},
            {"AgentExternalID", type nullable text},
            {"Direction", type text},
            {"Outcome", type text}
        },
        Text.From(FormatCheck[Culture])
    ),
    Seconds = Table.TransformColumns(
        TypedCore,
        {
            {"WaitSeconds", each fxParseSeconds(_, "WaitSeconds"), type number},
            {"TalkSeconds", each fxParseSeconds(_, "TalkSeconds"), type number},
            {"HoldSeconds", each fxParseSeconds(_, "HoldSeconds"), type number},
            {"AfterContactSeconds", each fxParseSeconds(_, "AfterContactSeconds"), type number}
        }
    ),
    WithSystem = Table.AddColumn(
        Seconds,
        "SystemKey",
        each Text.From(FormatCheck[SystemKey]),
        type text
    ),
    WithContactKey = Table.AddColumn(
        WithSystem,
        "ContactKey",
        each [SystemKey] & "|" & [SourceContactID],
        type text
    ),
    WithSourceDirection = Table.DuplicateColumn(
        WithContactKey,
        "Direction",
        "SourceDirection"
    ),
    WithSourceOutcome = Table.DuplicateColumn(
        WithSourceDirection,
        "Outcome",
        "SourceOutcome"
    ),
    MappedDirection = fxApplyValueMapping(
        WithSourceOutcome,
        p_Profile,
        Text.From(FormatCheck[SystemKey]),
        "ContactDirection",
        "Direction",
        p_AsOfDate
    ),
    MappedOutcome = fxApplyValueMapping(
        MappedDirection,
        p_Profile,
        Text.From(FormatCheck[SystemKey]),
        "ContactOutcome",
        "Outcome",
        p_AsOfDate
    ),
    Selected = Table.SelectColumns(
        MappedOutcome,
        {
            "ContactKey", "SystemKey", "SourceContactID", "ContactStart", "ContactEnd",
            "ChannelExternalID", "QueueExternalID", "AgentExternalID", "Direction", "Outcome",
            "SourceDirection", "SourceOutcome",
            "WaitSeconds", "TalkSeconds", "HoldSeconds", "AfterContactSeconds",
            "SourceFile", "SourceModifiedAt"
        }
    )
in
    Selected
