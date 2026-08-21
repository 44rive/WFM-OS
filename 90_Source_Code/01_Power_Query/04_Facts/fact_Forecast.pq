let
    Source = Table.SelectRows(
        stg_ForecastVersions,
        each [ApprovedFlag] and [ValidationStatus] = "VALID" and [Scenario] = "BASE"
    ),
    Selected = Table.SelectColumns(
        Source,
        {
            "ForecastRowKey", "ForecastVersionKey", "Scenario", "Method",
            "BusinessDate", "IntervalStart", "IntervalKey", "ActivityKey",
            "ChannelKey", "ForecastVolume", "ForecastAHTSeconds",
            "CreatedAt", "ApprovedAt", "ApprovedBy", "SourceRunKey"
        }
    ),
    Unique = fxAssertUnique(
        Selected,
        {"BusinessDate", "IntervalKey", "ActivityKey", "ChannelKey"},
        "fact_Forecast"
    )
in
    Unique
