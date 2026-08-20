let
    Index = Table.FromList({0..47}, Splitter.SplitByNothing(), {"IntervalIndex"}),
    Typed = Table.TransformColumnTypes(Index, {{"IntervalIndex", Int64.Type}}),
    IntervalKey = Table.AddColumn(
        Typed,
        "IntervalKey",
        each "I" & Text.PadStart(Text.From([IntervalIndex]), 2, "0"),
        type text
    ),
    StartTime = Table.AddColumn(
        IntervalKey,
        "StartTime",
        each #time(Number.IntegerDivide([IntervalIndex], 2), Number.Mod([IntervalIndex], 2) * 30, 0),
        type time
    ),
    Label = Table.AddColumn(StartTime, "IntervalLabel", each Time.ToText([StartTime], "HH:mm"), type text)
in
    Label
