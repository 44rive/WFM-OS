let
    Source = stg_Contacts,
    WindowStart = Date.AddMonths(p_AsOfDate, -Number.From(p_HistoryMonths)),
    Filtered = Table.SelectRows(
        Source,
        each [MappingStatus] = "Mapped"
            and [BusinessDate] >= WindowStart
            and [BusinessDate] < p_AsOfDate
    ),
    Selected = Table.SelectColumns(
        Filtered,
        {
            "ContactKey", "BusinessDate", "IntervalKey", "ActivityKey", "QueueKey",
            "ChannelKey", "AgentKey", "Offered", "Handled", "ShortAbandon",
            "SLEligibleOffered", "AnsweredWithinSL", "WaitSeconds", "HandleSeconds"
        }
    ),
    Unique = fxAssertUnique(Selected, {"ContactKey"}, "fact_ContactClosed")
in
    Unique
