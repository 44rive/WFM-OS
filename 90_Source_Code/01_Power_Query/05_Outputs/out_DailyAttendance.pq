let
    Operational = Table.Combine({fact_OperationalIntervalClosed, fact_OperationalIntervalLive}),
    DailyTotals = Table.Group(
        Operational,
        {"BusinessDate", "AgentKey"},
        {
            {"ScheduledSeconds", each List.Sum([ScheduledSeconds]), type number},
            {"PresentScheduledSeconds", each List.Sum([LoggedScheduledSeconds]), type number}
        }
    ),
    PaidSchedules = Table.SelectRows(stg_Schedules, each [MappingStatus] = "MAPPED" and [PaidFlag]),
    WithScheduleDate = Table.AddColumn(PaidSchedules, "BusinessDate", each Date.From([ScheduledStart]), type date),
    ScheduleEnvelope = Table.Group(
        WithScheduleDate,
        {"BusinessDate", "AgentKey"},
        {
            {"ScheduleStart", each List.Min([ScheduledStart]), type datetime},
            {"ScheduleEnd", each List.Max([ScheduledEnd]), type datetime}
        }
    ),
    ValidLogins = Table.SelectRows(stg_LoginSessions, each [MappingStatus] = "MAPPED"),
    WithLoginDate = Table.AddColumn(ValidLogins, "BusinessDate", each Date.From([LoginAt]), type date),
    LoginEnvelope = Table.Group(
        WithLoginDate,
        {"BusinessDate", "AgentKey"},
        {
            {"FirstLogin", each List.Min([LoginAt]), type datetime},
            {"LastLogout", each List.Max([LogoutAt]), type datetime}
        }
    ),
    WithSchedule = Table.NestedJoin(
        DailyTotals,
        {"BusinessDate", "AgentKey"},
        ScheduleEnvelope,
        {"BusinessDate", "AgentKey"},
        "Schedule",
        JoinKind.LeftOuter
    ),
    ExpandedSchedule = Table.ExpandTableColumn(
        WithSchedule,
        "Schedule",
        {"ScheduleStart", "ScheduleEnd"}
    ),
    WithLogin = Table.NestedJoin(
        ExpandedSchedule,
        {"BusinessDate", "AgentKey"},
        LoginEnvelope,
        {"BusinessDate", "AgentKey"},
        "Login",
        JoinKind.LeftOuter
    ),
    ExpandedLogin = Table.ExpandTableColumn(WithLogin, "Login", {"FirstLogin", "LastLogout"}),
    WithLate = Table.AddColumn(
        ExpandedLogin,
        "LateMinutes",
        each
            if [FirstLogin] = null then Number.RoundDown([ScheduledSeconds] / 60)
            else Number.RoundDown(List.Max({0, Duration.TotalMinutes([FirstLogin] - [ScheduleStart])})),
        Int64.Type
    ),
    WithEarly = Table.AddColumn(
        WithLate,
        "EarlyLeaveMinutes",
        each
            if [LastLogout] = null then 0
            else Number.RoundDown(List.Max({0, Duration.TotalMinutes([ScheduleEnd] - [LastLogout])})),
        Int64.Type
    ),
    WithRate = Table.AddColumn(
        WithEarly,
        "AttendanceRate",
        each if [ScheduledSeconds] = 0 then null else [PresentScheduledSeconds] / [ScheduledSeconds],
        type nullable number
    ),
    WithOutcome = Table.AddColumn(
        WithRate,
        "AttendanceOutcome",
        each
            if [PresentScheduledSeconds] = 0 then "ABSENT"
            else if [PresentScheduledSeconds] >= [ScheduledSeconds] then "PRESENT"
            else "PARTIAL",
        type text
    ),
    WithScheduledMinutes = Table.AddColumn(WithOutcome, "ScheduledMinutes", each [ScheduledSeconds] / 60, type number),
    WithPresentMinutes = Table.AddColumn(WithScheduledMinutes, "PresentScheduledMinutes", each [PresentScheduledSeconds] / 60, type number),
    Result = Table.SelectColumns(
        WithPresentMinutes,
        {
            "BusinessDate", "AgentKey", "ScheduledMinutes", "PresentScheduledMinutes",
            "LateMinutes", "EarlyLeaveMinutes", "AttendanceRate", "AttendanceOutcome"
        }
    )
in
    Result
