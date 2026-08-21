let
    Source = Table.SelectRows(
        stg_StaffingRequirements,
        each [MappingStatus] = "MAPPED" and [ApprovedFlag]
    ),
    WindowStart = Date.AddMonths(p_AsOfDate, -Number.From(p_HistoryMonths)),
    Filtered = Table.SelectRows(
        Source,
        each [BusinessDate] >= WindowStart and [BusinessDate] < p_AsOfDate
    ),
    Selected = Table.SelectColumns(
        Filtered,
        {
            "RequirementKey", "BusinessDate", "IntervalStart", "IntervalKey",
            "ActivityKey", "RequiredFTE", "RequirementVersion"
        }
    ),
    Unique = fxAssertUnique(
        Selected,
        {"BusinessDate", "IntervalStart", "ActivityKey"},
        "fact_StaffingRequirementClosed"
    )
in
    Unique
