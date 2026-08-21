let
    Source = Excel.CurrentWorkbook(){[Name = "tblPeople"]}[Content],
    Contract = fxAssertColumns(
        Source,
        {
            "Profile", "AgentKey", "EmployeeBusinessID", "DisplayName", "ActivityKey",
            "TeamKey", "ManagerKey", "SiteKey", "ContractHours", "ValidFrom",
            "ValidTo", "EmploymentStatus", "Enabled"
        },
        "tblPeople"
    ),
    Typed = Table.TransformColumnTypes(
        Contract,
        {
            {"AgentKey", type text}, {"ContractHours", type number},
            {"ValidFrom", type date}, {"ValidTo", type nullable date}
        }
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
        {
            "AgentKey", "EmployeeBusinessID", "DisplayName", "ActivityKey", "TeamKey",
            "ManagerKey", "SiteKey", "ContractHours", "EmploymentStatus"
        }
    ),
    Unique = fxAssertUnique(Selected, {"AgentKey"}, "dim_Agent")
in
    Unique
