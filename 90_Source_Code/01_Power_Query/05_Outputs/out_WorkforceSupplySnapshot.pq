let
    Source = dim_Agent,
    Grouped = Table.Group(
        Source,
        {"ActivityKey"},
        {
            {"ActiveHeads", each Table.RowCount(_), Int64.Type},
            {"ContractHours", each List.Sum([ContractHours]), type number}
        }
    ),
    WithOpeningPaidFTE = Table.AddColumn(
        Grouped,
        "OpeningPaidFTE",
        each [ContractHours] / p_StandardWeeklyHours,
        type number
    ),
    WithSnapshotDate = Table.AddColumn(
        WithOpeningPaidFTE,
        "SnapshotDate",
        each p_AsOfDate,
        type date
    ),
    Result = Table.ReorderColumns(
        WithSnapshotDate,
        {"SnapshotDate", "ActivityKey", "ActiveHeads", "ContractHours", "OpeningPaidFTE"}
    )
in
    Result
