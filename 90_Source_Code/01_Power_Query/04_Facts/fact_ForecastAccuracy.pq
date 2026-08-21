let
    Forecast = Table.SelectRows(fact_Forecast, each [BusinessDate] < p_AsOfDate),
    History = out_ForecastHistory,
    Joined = Table.NestedJoin(
        Forecast,
        {"BusinessDate", "IntervalKey", "ActivityKey", "ChannelKey"},
        History,
        {"Date", "IntervalKey", "ActivityKey", "ChannelKey"},
        "Actual",
        JoinKind.LeftOuter
    ),
    Expanded = Table.ExpandTableColumn(
        Joined,
        "Actual",
        {"Volume", "AHTSeconds"},
        {"ActualVolume", "ActualAHTSeconds"}
    ),
    Scorable = Table.SelectRows(Expanded, each [ActualVolume] <> null),
    WithSignedError = Table.AddColumn(
        Scorable,
        "SignedError",
        each [ForecastVolume] - [ActualVolume],
        type number
    ),
    WithAbsoluteError = Table.AddColumn(
        WithSignedError,
        "AbsoluteError",
        each Number.Abs([SignedError]),
        type number
    ),
    Result = Table.SelectColumns(
        WithAbsoluteError,
        {
            "ForecastVersionKey", "BusinessDate", "IntervalStart", "IntervalKey",
            "ActivityKey", "ChannelKey", "ActualVolume", "ForecastVolume",
            "SignedError", "AbsoluteError", "ActualAHTSeconds", "ForecastAHTSeconds"
        }
    ),
    Unique = fxAssertUnique(
        Result,
        {"ForecastVersionKey", "BusinessDate", "IntervalKey", "ActivityKey", "ChannelKey"},
        "fact_ForecastAccuracy"
    )
in
    Unique
