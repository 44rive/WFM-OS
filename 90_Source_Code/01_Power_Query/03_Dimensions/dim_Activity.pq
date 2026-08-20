let
    Source = Excel.CurrentWorkbook(){[Name = "tblActivities"]}[Content],
    Contract = fxAssertColumns(
        Source,
        {"Profile", "ActivityKey", "ActivityName", "ChannelKey", "Timezone", "ValidFrom", "ValidTo", "Enabled"},
        "tblActivities"
    ),
    Filtered = Table.SelectRows(
        Contract,
        each Text.From([Profile]) = p_Profile and fxAsLogical([Enabled])
    ),
    Selected = Table.SelectColumns(
        Filtered,
        {"ActivityKey", "ActivityName", "ChannelKey", "Timezone", "ValidFrom", "ValidTo"}
    ),
    Typed = Table.TransformColumnTypes(
        Selected,
        {{"ActivityKey", type text}, {"ValidFrom", type date}, {"ValidTo", type nullable date}}
    ),
    Unique = fxAssertUnique(Typed, {"ActivityKey"}, "dim_Activity")
in
    Unique
