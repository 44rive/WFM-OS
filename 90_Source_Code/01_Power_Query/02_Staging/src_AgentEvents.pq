let
    Config = fxGetSourceConfig("AgentEventSource"),
    Mapped = fxReadMappedEntity("AgentEventSource", "AgentEvent"),
    Contract = fxAssertColumns(
        Mapped,
        {
            "SourceAgentEventID", "AgentExternalID", "EventStart", "EventEnd",
            "StateExternalID", "SystemKey", "SourceCulture", "SourceFile", "SourceModifiedAt"
        },
        "AgentEvent adapter output"
    ),
    Culture = Text.From(Config[Culture]),
    Typed = Table.TransformColumnTypes(
        Contract,
        {
            {"SourceAgentEventID", type text}, {"AgentExternalID", type text},
            {"EventStart", type datetime}, {"EventEnd", type datetime},
            {"StateExternalID", type text}
        },
        Culture
    ),
    WithKey = Table.AddColumn(
        Typed,
        "AgentEventKey",
        each [SystemKey] & "|" & [SourceAgentEventID],
        type text
    ),
    Selected = Table.SelectColumns(
        WithKey,
        {
            "AgentEventKey", "SystemKey", "SourceAgentEventID", "AgentExternalID",
            "EventStart", "EventEnd", "StateExternalID", "SourceFile", "SourceModifiedAt"
        }
    )
in
    Selected
