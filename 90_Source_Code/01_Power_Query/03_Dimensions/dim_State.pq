let
    Source = Excel.CurrentWorkbook(){[Name = "tblStateMapping"]}[Content],
    Contract = fxAssertColumns(
        Source,
        {
            "Profile", "StateKey", "StateName", "AdherenceClass", "PresentFlag",
            "ProductiveFlag", "ValidFrom", "ValidTo", "Enabled"
        },
        "tblStateMapping"
    ),
    Typed = Table.TransformColumnTypes(
        Contract,
        {{"StateKey", type text}, {"ValidFrom", type date}, {"ValidTo", type nullable date}}
    ),
    Active = Table.SelectRows(
        Typed,
        each Text.From([Profile]) = p_Profile
            and fxAsLogical([Enabled])
            and [ValidFrom] <= p_AsOfDate
            and ([ValidTo] = null or [ValidTo] >= p_AsOfDate)
    ),
    Selected = Table.SelectColumns(
        Active,
        {"StateKey", "StateName", "AdherenceClass", "PresentFlag", "ProductiveFlag"}
    ),
    Logical = Table.TransformColumns(
        Selected,
        {
            {"PresentFlag", each fxAsLogical(_), type logical},
            {"ProductiveFlag", each fxAsLogical(_), type logical}
        }
    ),
    Distinct = Table.Distinct(Logical),
    Unique = fxAssertUnique(Distinct, {"StateKey"}, "dim_State")
in
    Unique
