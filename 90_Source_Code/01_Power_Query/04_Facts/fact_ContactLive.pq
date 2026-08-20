let
    Source = stg_Contacts,
    Filtered = Table.SelectRows(
        Source,
        each [MappingStatus] = "Mapped" and [BusinessDate] = p_AsOfDate
    ),
    Selected = Table.SelectColumns(
        Filtered,
        {
            "ContactKey", "BusinessDate", "IntervalKey", "ActivityKey", "QueueKey",
            "ChannelKey", "AgentKey", "Offered", "Handled", "ShortAbandon",
            "SLEligibleOffered", "AnsweredWithinSL", "WaitSeconds", "HandleSeconds"
        }
    ),
    Unique = fxAssertUnique(Selected, {"ContactKey"}, "fact_ContactLive")
in
    Unique
