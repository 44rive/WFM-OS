let
    Source = Excel.CurrentWorkbook(){[Name = "tblQueueMapping"]}[Content],
    Contract = fxAssertColumns(
        Source,
        {
            "Profile", "QueueKey", "QueueName", "ActivityKey", "ChannelKey",
            "ValidFrom", "ValidTo", "Enabled"
        },
        "tblQueueMapping"
    ),
    Filtered = Table.SelectRows(
        Contract,
        each Text.From([Profile]) = p_Profile and fxAsLogical([Enabled])
    ),
    Selected = Table.SelectColumns(
        Filtered,
        {"QueueKey", "QueueName", "ActivityKey", "ChannelKey", "ValidFrom", "ValidTo"}
    ),
    Typed = Table.TransformColumnTypes(
        Selected,
        {{"QueueKey", type text}, {"ValidFrom", type date}, {"ValidTo", type nullable date}}
    ),
    Unique = fxAssertUnique(Typed, {"QueueKey"}, "dim_Queue")
in
    Unique
