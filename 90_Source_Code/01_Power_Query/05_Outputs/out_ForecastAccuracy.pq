let
    Source = fact_ForecastAccuracy,
    Grouped = Table.Group(
        Source,
        {"ForecastVersionKey", "BusinessDate", "ActivityKey", "ChannelKey"},
        {
            {"ActualVolume", each List.Sum([ActualVolume]), type number},
            {"ForecastVolume", each List.Sum([ForecastVolume]), type number},
            {"SignedError", each List.Sum([SignedError]), type number},
            {"AbsoluteError", each List.Sum([AbsoluteError]), type number}
        }
    ),
    WithWAPE = Table.AddColumn(
        Grouped,
        "WAPE",
        each if [ActualVolume] = 0 then null else [AbsoluteError] / [ActualVolume],
        type nullable number
    ),
    WithBias = Table.AddColumn(
        WithWAPE,
        "SignedBias",
        each if [ActualVolume] = 0 then null else [SignedError] / [ActualVolume],
        type nullable number
    )
in
    WithBias
