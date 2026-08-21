let
    Source = fact_ContactClosed,
    Grouped = Table.Group(
        Source,
        {"BusinessDate", "IntervalKey", "ActivityKey", "ChannelKey"},
        {
            {"Volume", each List.Sum([Offered]), type number},
            {"Handled", each List.Sum([Handled]), type number},
            {"HandleSeconds", each List.Sum([HandleSeconds]), type number}
        }
    ),
    WithAHT = Table.AddColumn(
        Grouped,
        "AHTSeconds",
        each if [Handled] = 0 then null else [HandleSeconds] / [Handled],
        type nullable number
    ),
    WithDate = Table.AddColumn(WithAHT, "Date", each [BusinessDate], type date),
    WithIntervalStart = Table.AddColumn(
        WithDate,
        "IntervalStart",
        each
            let
                IntervalIndex = Number.FromText(Text.AfterDelimiter([IntervalKey], "I"))
            in
                #datetime(
                    Date.Year([BusinessDate]),
                    Date.Month([BusinessDate]),
                    Date.Day([BusinessDate]),
                    0,
                    0,
                    0
                )
                    + #duration(
                        0,
                        Number.IntegerDivide(IntervalIndex, 2),
                        Number.Mod(IntervalIndex, 2) * 30,
                        0
                    ),
        type datetime
    ),
    Result = Table.SelectColumns(
        WithIntervalStart,
        {
            "Date", "IntervalStart", "IntervalKey", "ActivityKey", "ChannelKey",
            "Volume", "Handled", "HandleSeconds", "AHTSeconds"
        }
    )
in
    Result
