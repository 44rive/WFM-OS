let
    Config = fxGetSourceConfig("StaffingRequirementSource"),
    Mapped = fxReadMappedEntity("StaffingRequirementSource", "StaffingRequirement"),
    Contract = fxAssertColumns(
        Mapped,
        {
            "SourceRequirementID", "IntervalStart", "ActivityExternalID", "RequiredFTE",
            "ApprovedFlag", "SystemKey", "SourceCulture", "SourceFile", "SourceModifiedAt"
        },
        "StaffingRequirement adapter output"
    ),
    WithVersion =
        if List.Contains(Table.ColumnNames(Contract), "RequirementVersion") then Contract
        else Table.AddColumn(Contract, "RequirementVersion", each null, type nullable text),
    Culture = Text.From(Config[Culture]),
    Typed = Table.TransformColumnTypes(
        WithVersion,
        {
            {"SourceRequirementID", type text}, {"IntervalStart", type datetime},
            {"ActivityExternalID", type text}, {"RequiredFTE", type number},
            {"RequirementVersion", type nullable text}
        },
        Culture
    ),
    Approved = Table.TransformColumns(
        Typed,
        {{"ApprovedFlag", each fxAsLogical(_), type logical}}
    ),
    WithKey = Table.AddColumn(
        Approved,
        "RequirementKey",
        each [SystemKey] & "|" & [SourceRequirementID],
        type text
    ),
    Selected = Table.SelectColumns(
        WithKey,
        {
            "RequirementKey", "SystemKey", "SourceRequirementID", "IntervalStart",
            "ActivityExternalID", "RequiredFTE", "RequirementVersion", "ApprovedFlag",
            "SourceFile", "SourceModifiedAt"
        }
    )
in
    Selected
