let
    Source = Excel.CurrentWorkbook(){[Name = "tblScheduleAuthority"]}[Content],
    Contract = fxAssertColumns(
        Source,
        {
            "Profile", "AuthorityKey", "ActivityKey", "ValidFrom", "ValidTo",
            "ScheduleAuthority", "RosterVersionKey", "PublicationVersionKey", "Approved", "Owner", "Notes"
        },
        "tblScheduleAuthority"
    ),
    NonBlank = Table.SelectRows(Contract, each [AuthorityKey] <> null and Text.Trim(Text.From([AuthorityKey])) <> ""),
    Typed = Table.TransformColumnTypes(
        NonBlank,
        {
            {"Profile", type text}, {"AuthorityKey", type text}, {"ActivityKey", type text},
            {"ValidFrom", type date}, {"ValidTo", type nullable date},
            {"ScheduleAuthority", type text}, {"RosterVersionKey", type nullable text},
            {"PublicationVersionKey", type nullable text},
            {"Owner", type nullable text}, {"Notes", type nullable text}
        }
    ),
    Normalized = Table.TransformColumns(
        Typed,
        {
            {"Approved", each fxAsLogical(_), type logical},
            {"ScheduleAuthority", each Text.Upper(Text.Trim(Text.From(_))), type text}
        }
    ),
    ProfileRows = Table.SelectRows(Normalized, each [Profile] = p_Profile),
    WithRangeCount = Table.AddColumn(
        ProfileRows,
        "AuthorityRangeCount",
        (CurrentRow as record) as number => Table.RowCount(
            Table.SelectRows(
                ProfileRows,
                (OtherRow as record) as logical =>
                    OtherRow[Approved]
                        and CurrentRow[Approved]
                        and OtherRow[ActivityKey] = CurrentRow[ActivityKey]
                        and OtherRow[ValidFrom] <> null
                        and CurrentRow[ValidFrom] <> null
                        and OtherRow[ValidFrom] <= (if CurrentRow[ValidTo] = null then #date(9999, 12, 31) else CurrentRow[ValidTo])
                        and CurrentRow[ValidFrom] <= (if OtherRow[ValidTo] = null then #date(9999, 12, 31) else OtherRow[ValidTo])
            )
        ),
        Int64.Type
    ),
    WithValidation = Table.AddColumn(
        WithRangeCount,
        "ValidationStatus",
        each
            if not [Approved] then "NOT_APPLICABLE"
            else if [ActivityKey] = null or Text.Trim([ActivityKey]) = "" then "MISSING_ACTIVITY"
            else if [ValidFrom] = null or ([ValidTo] <> null and [ValidTo] < [ValidFrom]) then "INVALID_EFFECTIVE_RANGE"
            else if not List.Contains({"IMPORTED_SCHEDULE", "PUBLISHED_ROSTER"}, [ScheduleAuthority]) then "INVALID_SCHEDULE_AUTHORITY"
            else if [ScheduleAuthority] = "PUBLISHED_ROSTER" and ([RosterVersionKey] = null or Text.Trim([RosterVersionKey]) = "") then "MISSING_ROSTER_VERSION"
            else if [ScheduleAuthority] = "PUBLISHED_ROSTER" and ([PublicationVersionKey] = null or Text.Trim([PublicationVersionKey]) = "") then "MISSING_PUBLICATION_VERSION"
            else if [ScheduleAuthority] = "IMPORTED_SCHEDULE" and (([RosterVersionKey] <> null and Text.Trim([RosterVersionKey]) <> "") or ([PublicationVersionKey] <> null and Text.Trim([PublicationVersionKey]) <> "")) then "IMPORTED_AUTHORITY_HAS_PUBLICATION_LINEAGE"
            else if [AuthorityRangeCount] <> 1 then "OVERLAPPING_SCHEDULE_AUTHORITY"
            else "VALID",
        type text
    )
in
    WithValidation
