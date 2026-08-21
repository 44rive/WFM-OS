let
    Source = src_AgentEvents,
    IdentityResolved = fxResolveIdentity(Source, "AgentExternalID", "EventStart"),
    StateResolved = fxResolveState(IdentityResolved, "StateExternalID", "EventStart"),
    Flags = Table.TransformColumns(
        StateResolved,
        {
            {"StatePresentFlag", each if _ = null then null else fxAsLogical(_), type nullable logical},
            {"StateProductiveFlag", each if _ = null then null else fxAsLogical(_), type nullable logical}
        }
    ),
    WithRangeStatus = Table.AddColumn(
        Flags,
        "RangeStatus",
        each if [EventEnd] > [EventStart] then "VALID" else "INVALID_TIME_RANGE",
        type text
    ),
    WithMappingStatus = Table.AddColumn(
        WithRangeStatus,
        "MappingStatus",
        each
            if [RangeStatus] <> "VALID" then [RangeStatus]
            else if [IdentityStatus] <> "RESOLVED" then [IdentityStatus]
            else if [StateStatus] <> "RESOLVED" then [StateStatus]
            else "MAPPED",
        type text
    ),
    Result = Table.AddColumn(
        WithMappingStatus,
        "MappingValue",
        each
            if [IdentityStatus] <> "RESOLVED" then [IdentityValue]
            else if [StateStatus] <> "RESOLVED" then [StateValue]
            else null,
        type nullable text
    )
in
    Result
