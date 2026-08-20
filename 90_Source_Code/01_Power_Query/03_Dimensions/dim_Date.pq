let
    StartDate = Date.StartOfMonth(Date.AddMonths(p_AsOfDate, -Number.From(p_HistoryMonths))),
    EndDate = Date.EndOfMonth(Date.AddMonths(p_AsOfDate, 24)),
    Dates = List.Dates(
        StartDate,
        Duration.Days(EndDate - StartDate) + 1,
        #duration(1, 0, 0, 0)
    ),
    AsTable = Table.FromList(Dates, Splitter.SplitByNothing(), {"Date"}),
    Typed = Table.TransformColumnTypes(AsTable, {{"Date", type date}}),
    DateKey = Table.AddColumn(
        Typed,
        "DateKey",
        each Date.Year([Date]) * 10000 + Date.Month([Date]) * 100 + Date.Day([Date]),
        Int64.Type
    ),
    Year = Table.AddColumn(DateKey, "Year", each Date.Year([Date]), Int64.Type),
    Quarter = Table.AddColumn(Year, "Quarter", each "Q" & Text.From(Date.QuarterOfYear([Date])), type text),
    MonthNumber = Table.AddColumn(Quarter, "MonthNumber", each Date.Month([Date]), Int64.Type),
    Month = Table.AddColumn(MonthNumber, "Month", each Date.ToText([Date], "MMM"), type text),
    YearMonth = Table.AddColumn(Month, "YearMonth", each Date.ToText([Date], "yyyy-MM"), type text),
    WeekStart = Table.AddColumn(YearMonth, "WeekStart", each Date.StartOfWeek([Date], Day.Monday), type date),
    WeekdayNumber = Table.AddColumn(WeekStart, "WeekdayNumber", each Date.DayOfWeek([Date], Day.Monday) + 1, Int64.Type),
    Weekday = Table.AddColumn(WeekdayNumber, "Weekday", each Date.ToText([Date], "ddd"), type text),
    IsLiveDate = Table.AddColumn(Weekday, "IsLiveDate", each [Date] = p_AsOfDate, type logical)
in
    IsLiveDate
