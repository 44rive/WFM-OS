let
    Source = Excel.CurrentWorkbook(){[Name = "tblActionInput"]}[Content],
    Contract = fxAssertColumns(
        Source,
        {"ActionKey", "OpenedAt", "Module", "Severity", "Action", "Owner", "DueAt", "Status", "Outcome", "ClosedAt"},
        "tblActionInput"
    ),
    NonBlank = Table.SelectRows(Contract, each Text.Trim(Text.From([ActionKey])) <> ""),
    Typed = Table.TransformColumnTypes(
        NonBlank,
        {{"OpenedAt", type nullable datetime}, {"DueAt", type nullable datetime}, {"ClosedAt", type nullable datetime}}
    ),
    WithDueState = Table.AddColumn(
        Typed,
        "DueState",
        each
            if List.Contains({"COMPLETED", "CANCELLED"}, Text.Upper(Text.From([Status]))) then "CLOSED"
            else if [DueAt] = null then "NO_DUE_DATE"
            else if [DueAt] < DateTime.LocalNow() then "OVERDUE"
            else if Date.From([DueAt]) = Date.From(DateTime.LocalNow()) then "DUE_TODAY"
            else "OPEN",
        type text
    )
in
    WithDueState
