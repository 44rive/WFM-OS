let
    Source = src_LoginSessions,
    Resolved = fxResolveIdentity(Source, "AgentExternalID", "LoginAt"),
    WithRangeStatus = Table.AddColumn(
        Resolved,
        "RangeStatus",
        each if [LogoutAt] > [LoginAt] then "VALID" else "INVALID_TIME_RANGE",
        type text
    ),
    WithMappingStatus = Table.AddColumn(
        WithRangeStatus,
        "MappingStatus",
        each
            if [RangeStatus] <> "VALID" then [RangeStatus]
            else if [IdentityStatus] <> "RESOLVED" then [IdentityStatus]
            else "MAPPED",
        type text
    ),
    Result = Table.AddColumn(
        WithMappingStatus,
        "MappingValue",
        each if [IdentityStatus] <> "RESOLVED" then [IdentityValue] else null,
        type nullable text
    )
in
    Result
