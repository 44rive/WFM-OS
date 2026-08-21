let
    Config = fxGetSourceConfig("SchedulingTool"),
    Mapped = fxReadMappedEntity("SchedulingTool", "ScheduleSegment"),
    Contract = fxAssertColumns(
        Mapped,
        {
            "SourceScheduleSegmentID", "AgentExternalID", "ScheduledStart", "ScheduledEnd",
            "ActivityExternalID", "ScheduleTypeExternalID", "PaidFlag", "ProductiveFlag",
            "SystemKey", "SourceCulture", "SourceFile", "SourceModifiedAt"
        },
        "ScheduleSegment adapter output"
    ),
    Culture = Text.From(Config[Culture]),
    Typed = Table.TransformColumnTypes(
        Contract,
        {
            {"SourceScheduleSegmentID", type text}, {"AgentExternalID", type text},
            {"ScheduledStart", type datetime}, {"ScheduledEnd", type datetime},
            {"ActivityExternalID", type text}, {"ScheduleTypeExternalID", type text}
        },
        Culture
    ),
    Flags = Table.TransformColumns(
        Typed,
        {
            {"PaidFlag", each fxAsLogical(_), type logical},
            {"ProductiveFlag", each fxAsLogical(_), type logical}
        }
    ),
    WithKey = Table.AddColumn(
        Flags,
        "ScheduleSegmentKey",
        each [SystemKey] & "|" & [SourceScheduleSegmentID],
        type text
    ),
    Selected = Table.SelectColumns(
        WithKey,
        {
            "ScheduleSegmentKey", "SystemKey", "SourceScheduleSegmentID", "AgentExternalID",
            "ScheduledStart", "ScheduledEnd", "ActivityExternalID", "ScheduleTypeExternalID",
            "PaidFlag", "ProductiveFlag", "SourceFile", "SourceModifiedAt"
        }
    )
in
    Selected
