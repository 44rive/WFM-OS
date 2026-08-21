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
    ApprovedBaseRows = Table.SelectRows(
        stg_RequirementApprovals,
        each [ScenarioKey] = "BASE"
    ),
    ApprovedWorkbook = Table.SelectColumns(
        ApprovedBaseRows,
        Columns,
        MissingField.UseNull
    ),
    Combined = Table.Combine({External, ApprovedWorkbook})
in
    Combined
