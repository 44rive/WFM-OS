let
    Source = stg_Contacts,
    Grouped = Table.Group(
        Source,
        {"BusinessDate"},
        {
            {"SourceRows", each Table.RowCount(_), Int64.Type},
            {"InboundOffered", each List.Sum([Offered]), Int64.Type},
            {"MappedInbound", each List.Sum(Table.SelectRows(_, each [MappingStatus] = "Mapped")[Offered]), Int64.Type},
            {"Handled", each List.Sum(Table.SelectRows(_, each [MappingStatus] = "Mapped")[Handled]), Int64.Type},
            {"UnmappedRows", each Table.RowCount(Table.SelectRows(_, each [MappingStatus] <> "Mapped")), Int64.Type}
        }
    ),
    Difference = Table.AddColumn(
        Grouped,
        "OfferedDifference",
        each [InboundOffered] - [MappedInbound],
        Int64.Type
    ),
    Status = Table.AddColumn(
        Difference,
        "Status",
        each if [OfferedDifference] = 0 and [UnmappedRows] = 0 then "PASS" else "FAIL",
        type text
    ),
    Ordered = Table.ReorderColumns(
        Status,
        {
            "BusinessDate", "Status", "SourceRows", "InboundOffered",
            "MappedInbound", "OfferedDifference", "Handled", "UnmappedRows"
        }
    )
in
    Ordered
