let
    Config = fxGetSourceConfig("LoginSource"),
    Mapped = fxReadMappedEntity("LoginSource", "LoginSession"),
    Contract = fxAssertColumns(
        Mapped,
        {
            "SourceLoginSessionID", "AgentExternalID", "LoginAt", "LogoutAt",
            "SystemKey", "SourceCulture", "SourceFile", "SourceModifiedAt"
        },
        "LoginSession adapter output"
    ),
    Culture = Text.From(Config[Culture]),
    Typed = Table.TransformColumnTypes(
        Contract,
        {
            {"SourceLoginSessionID", type text}, {"AgentExternalID", type text},
            {"LoginAt", type datetime}, {"LogoutAt", type datetime}
        },
        Culture
    ),
    WithKey = Table.AddColumn(
        Typed,
        "LoginSessionKey",
        each [SystemKey] & "|" & [SourceLoginSessionID],
        type text
    ),
    Selected = Table.SelectColumns(
        WithKey,
        {
            "LoginSessionKey", "SystemKey", "SourceLoginSessionID", "AgentExternalID",
            "LoginAt", "LogoutAt", "SourceFile", "SourceModifiedAt"
        }
    )
in
    Selected
