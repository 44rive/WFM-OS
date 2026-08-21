let
    Source = Table.Combine({fact_OperationalIntervalClosed, fact_OperationalIntervalLive}),
    WithConformance = Table.AddColumn(
        Source,
        "ConformanceRate",
        each if [ScheduledSeconds] = 0 then null else [LoggedScheduledSeconds] / [ScheduledSeconds],
        type nullable number
    ),
    WithAdherence = Table.AddColumn(
        WithConformance,
        "AdherenceRate",
        each if [ScheduledSeconds] = 0 then null else [AdherentSeconds] / [ScheduledSeconds],
        type nullable number
    ),
    Exceptions = Table.SelectRows(WithAdherence, each [ExceptionSeconds] > 0),
    Result = Table.SelectColumns(
        Exceptions,
        {
            "BusinessDate", "IntervalStart", "IntervalKey", "ActivityKey", "AgentKey",
            "ScheduledSeconds", "LoggedScheduledSeconds", "AdherentSeconds",
            "ExceptionSeconds", "ConformanceRate", "AdherenceRate"
        }
    )
in
    Result
