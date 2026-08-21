let
    Columns = {
        "RequirementKey", "BusinessDate", "IntervalStart", "IntervalKey",
        "ActivityKey", "RequiredFTE", "RequirementVersion", "ApprovedFlag",
        "MappingStatus", "MappingValue"
    },
    External = Table.SelectColumns(
        stg_StaffingRequirements,
        Columns,
        MissingField.UseNull
    ),
    ApprovedWorkbook = Table.SelectColumns(
        stg_RequirementApprovals,
        Columns,
        MissingField.UseNull
    ),
    Combined = Table.Combine({External, ApprovedWorkbook})
in
    Combined
