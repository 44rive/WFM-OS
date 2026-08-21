let
    Source = Table.SelectRows(
        stg_StaffingRequirements,
        each [MappingStatus] = "MAPPED" and [ApprovedFlag] and [BusinessDate] = p_AsOfDate
    ),
    Selected = Table.SelectColumns(
        Source,
        {
            "RequirementKey", "BusinessDate", "IntervalStart", "IntervalKey",
            "ActivityKey", "RequiredFTE", "RequirementVersion"
        }
    ),
    Unique = fxAssertUnique(
        Selected,
        {"BusinessDate", "IntervalStart", "ActivityKey"},
        "fact_StaffingRequirementLive"
    )
in
    Unique
