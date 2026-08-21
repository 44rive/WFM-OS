(Input as table, StartColumn as text, EndColumn as text, optional IntervalMinutes as nullable number) as table =>
let
    SizeMinutes = if IntervalMinutes = null then 30 else Number.From(IntervalMinutes),
    IntervalDuration = #duration(0, 0, SizeMinutes, 0),
    WithIntervals = Table.AddColumn(
        Input,
        "IntervalRows",
        (Current as record) as table =>
            let
                RangeStart = DateTime.From(Record.Field(Current, StartColumn)),
                RangeEnd = DateTime.From(Record.Field(Current, EndColumn)),
                FirstStart = #datetime(
                    Date.Year(Date.From(RangeStart)),
                    Date.Month(Date.From(RangeStart)),
                    Date.Day(Date.From(RangeStart)),
                    Time.Hour(Time.From(RangeStart)),
                    Number.IntegerDivide(Time.Minute(Time.From(RangeStart)), SizeMinutes) * SizeMinutes,
                    0
                ),
                Starts =
                    if RangeEnd <= RangeStart then {}
                    else List.Generate(
                        () => FirstStart,
                        each _ < RangeEnd,
                        each _ + IntervalDuration
                    ),
                Records = List.Transform(
                    Starts,
                    (IntervalStart as datetime) as record =>
                        [
                            IntervalStart = IntervalStart,
                            IntervalEnd = IntervalStart + IntervalDuration,
                            OverlapSeconds = fxOverlapSeconds(
                                RangeStart,
                                RangeEnd,
                                IntervalStart,
                                IntervalStart + IntervalDuration
                            ),
                            BusinessDate = Date.From(IntervalStart),
                            IntervalKey = "I" & Text.PadStart(
                                Text.From(
                                    Time.Hour(Time.From(IntervalStart)) * (60 / SizeMinutes)
                                        + Number.IntegerDivide(Time.Minute(Time.From(IntervalStart)), SizeMinutes)
                                ),
                                2,
                                "0"
                            )
                        ]
                ),
                Result = Table.FromRecords(
                    Records,
                    type table [
                        IntervalStart = datetime,
                        IntervalEnd = datetime,
                        OverlapSeconds = number,
                        BusinessDate = date,
                        IntervalKey = text
                    ]
                )
            in
                Result,
        type table
    ),
    Expanded = Table.ExpandTableColumn(
        WithIntervals,
        "IntervalRows",
        {"IntervalStart", "IntervalEnd", "OverlapSeconds", "BusinessDate", "IntervalKey"}
    )
in
    Expanded
