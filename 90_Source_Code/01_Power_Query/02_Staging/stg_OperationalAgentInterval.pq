let
    Schedules = stg_AuthoritativeScheduleIntervals,
    Logins = stg_LoginIntervals,
    Events = stg_AgentEventIntervals,
    WithLoginRows = Table.NestedJoin(
        Schedules,
        {"AgentKey", "IntervalStart"},
        Logins,
        {"AgentKey", "IntervalStart"},
        "LoginRows",
        JoinKind.LeftOuter
    ),
    WithLogged = Table.AddColumn(
        WithLoginRows,
        "LoggedScheduledSecondsRaw",
        (ScheduleRow as record) as number =>
            List.Sum(
                {0} & List.Transform(
                    Table.ToRecords(ScheduleRow[LoginRows]),
                    (LoginRow as record) as number => fxOverlapSeconds(
                        ScheduleRow[ScheduledStart],
                        ScheduleRow[ScheduledEnd],
                        LoginRow[LoginAt],
                        LoginRow[LogoutAt]
                    )
                )
            ),
        type number
    ),
    WithoutLoginRows = Table.RemoveColumns(WithLogged, {"LoginRows"}),
    WithEventRows = Table.NestedJoin(
        WithoutLoginRows,
        {"AgentKey", "IntervalStart"},
        Events,
        {"AgentKey", "IntervalStart"},
        "EventRows",
        JoinKind.LeftOuter
    ),
    WithProductive = Table.AddColumn(
        WithEventRows,
        "ProductiveActualSecondsRaw",
        (ScheduleRow as record) as number =>
            List.Sum(
                {0} & List.Transform(
                    Table.ToRecords(ScheduleRow[EventRows]),
                    (EventRow as record) as number =>
                        if ScheduleRow[PaidFlag]
                            and ScheduleRow[ProductiveFlag]
                            and EventRow[StateProductiveFlag]
                        then fxOverlapSeconds(
                            ScheduleRow[ScheduledStart],
                            ScheduleRow[ScheduledEnd],
                            EventRow[EventStart],
                            EventRow[EventEnd]
                        )
                        else 0
                )
            ),
        type number
    ),
    WithAdherent = Table.AddColumn(
        WithProductive,
        "AdherentSecondsRaw",
        (ScheduleRow as record) as number =>
            List.Sum(
                {0} & List.Transform(
                    Table.ToRecords(ScheduleRow[EventRows]),
                    (EventRow as record) as number =>
                        if ScheduleRow[PaidFlag]
                            and (
                                (ScheduleRow[ProductiveFlag] and EventRow[StateProductiveFlag])
                                or Text.Upper(Text.From(ScheduleRow[ScheduleTypeKey]))
                                    = Text.Upper(Text.From(EventRow[StateKey]))
                            )
                        then fxOverlapSeconds(
                            ScheduleRow[ScheduledStart],
                            ScheduleRow[ScheduledEnd],
                            EventRow[EventStart],
                            EventRow[EventEnd]
                        )
                        else 0
                )
            ),
        type number
    ),
    WithoutEventRows = Table.RemoveColumns(WithAdherent, {"EventRows"}),
    Grouped = Table.Group(
        WithoutEventRows,
        {"BusinessDate", "IntervalStart", "IntervalKey", "ActivityKey", "AgentKey"},
        {
            {"ScheduledSeconds", each List.Sum([ScheduledSeconds]), type number},
            {"ScheduledProductiveSeconds", each List.Sum([ScheduledProductiveSeconds]), type number},
            {"LoggedScheduledSecondsRaw", each List.Sum([LoggedScheduledSecondsRaw]), type number},
            {"ProductiveActualSecondsRaw", each List.Sum([ProductiveActualSecondsRaw]), type number},
            {"AdherentSecondsRaw", each List.Sum([AdherentSecondsRaw]), type number}
        }
    ),
    WithLoggedCap = Table.AddColumn(
        Grouped,
        "LoggedScheduledSeconds",
        each List.Min({[ScheduledSeconds], [LoggedScheduledSecondsRaw]}),
        type number
    ),
    WithProductiveCap = Table.AddColumn(
        WithLoggedCap,
        "ProductiveActualSeconds",
        each List.Min({[ScheduledProductiveSeconds], [ProductiveActualSecondsRaw]}),
        type number
    ),
    WithAdherentCap = Table.AddColumn(
        WithProductiveCap,
        "AdherentSeconds",
        each List.Min({[ScheduledSeconds], [AdherentSecondsRaw]}),
        type number
    ),
    WithException = Table.AddColumn(
        WithAdherentCap,
        "ExceptionSeconds",
        each List.Max({0, [ScheduledSeconds] - [AdherentSeconds]}),
        type number
    ),
    Result = Table.RemoveColumns(
        WithException,
        {"LoggedScheduledSecondsRaw", "ProductiveActualSecondsRaw", "AdherentSecondsRaw"}
    )
in
    Result
