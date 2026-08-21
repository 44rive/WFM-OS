let
    Source = dim_Activity,
    Selected = Table.SelectColumns(Source, {"ChannelKey"}),
    NonBlank = Table.SelectRows(
        Selected,
        each [ChannelKey] <> null and Text.Trim(Text.From([ChannelKey])) <> ""
    ),
    Distinct = Table.Distinct(NonBlank),
    WithName = Table.AddColumn(Distinct, "ChannelName", each [ChannelKey], type text),
    Unique = fxAssertUnique(WithName, {"ChannelKey"}, "dim_Channel")
in
    Unique
