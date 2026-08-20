let
    Source = stg_Contacts,
    Summary = Table.Group(
        Source,
        {"MappingStatus", "MappingValue", "SourceFile"},
        {
            {"Rows", each Table.RowCount(_), Int64.Type},
            {"FirstContact", each List.Min([ContactStart]), type datetime},
            {"LastContact", each List.Max([ContactStart]), type datetime}
        }
    ),
    Severity = Table.AddColumn(
        Summary,
        "Severity",
        each if [MappingStatus] = "Mapped" then "OK" else "BLOCKING",
        type text
    ),
    Ordered = Table.ReorderColumns(
        Severity,
        {"Severity", "MappingStatus", "MappingValue", "Rows", "SourceFile", "FirstContact", "LastContact"}
    )
in
    Ordered
