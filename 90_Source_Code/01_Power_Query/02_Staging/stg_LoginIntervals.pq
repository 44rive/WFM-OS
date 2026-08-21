let
    Source = Table.SelectRows(stg_LoginSessions, each [MappingStatus] = "MAPPED"),
    Unique = fxAssertUnique(Source, {"LoginSessionKey"}, "stg_LoginSessions"),
    Result = fxExpandIntervals(Unique, "LoginAt", "LogoutAt", 30)
in
    Result
