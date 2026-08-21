let
    ImportedBase = Table.SelectColumns(
        stg_ScheduleIntervals,
        {
            "BusinessDate", "IntervalStart", "IntervalKey", "AgentKey", "ActivityKey",
            "ScheduledStart", "ScheduledEnd", "ScheduleTypeKey", "PaidFlag", "ProductiveFlag",
            "ScheduledSeconds", "ScheduledProductiveSeconds"
        }
    ),
    ImportedWithRoster = Table.AddColumn(ImportedBase, "RosterVersionKey", each null, type nullable text),
    ImportedWithPublication = Table.AddColumn(ImportedWithRoster, "PublicationVersionKey", each null, type nullable text),
    Imported = Table.AddColumn(ImportedWithPublication, "ScheduleAuthority", each "IMPORTED_SCHEDULE", type text),
    PublishedBase = Table.SelectColumns(
        fact_PublishedRosterSegment,
        {
            "PublicationVersionKey", "RosterVersionKey", "BusinessDate", "IntervalStart", "IntervalKey", "AgentKey", "ActivityKey",
            "ScheduleTypeKey", "PaidFlag", "ProductiveFlag", "ScheduledSeconds"
        }
    ),
    PublishedWithStart = Table.AddColumn(PublishedBase, "ScheduledStart", each [IntervalStart], type datetime),
    PublishedWithEnd = Table.AddColumn(PublishedWithStart, "ScheduledEnd", each [IntervalStart] + #duration(0, 0, 30, 0), type datetime),
    PublishedWithProductive = Table.AddColumn(PublishedWithEnd, "ScheduledProductiveSeconds", each if [PaidFlag] and [ProductiveFlag] then [ScheduledSeconds] else 0, type number),
    Published = Table.AddColumn(PublishedWithProductive, "ScheduleAuthority", each "PUBLISHED_ROSTER", type text),
    Combined = Table.Combine({Imported, Published}),
    ApprovedAuthority = Table.SelectRows(stg_ScheduleAuthority, each [Approved] and [ValidationStatus] = "VALID"),
    WithAuthority = Table.AddColumn(
        Combined,
        "AuthorityMatch",
        each let
            CurrentDate = [BusinessDate],
            CurrentActivity = [ActivityKey],
            CurrentAuthority = [ScheduleAuthority],
            CurrentRoster = [RosterVersionKey],
            CurrentPublication = [PublicationVersionKey]
        in
            Table.SelectRows(
                ApprovedAuthority,
                (AuthorityRow) =>
                    AuthorityRow[ActivityKey] = CurrentActivity
                        and AuthorityRow[ScheduleAuthority] = CurrentAuthority
                        and (
                            CurrentAuthority <> "PUBLISHED_ROSTER"
                                or (
                                    AuthorityRow[RosterVersionKey] = CurrentRoster
                                        and AuthorityRow[PublicationVersionKey] = CurrentPublication
                                )
                        )
                        and AuthorityRow[ValidFrom] <= CurrentDate
                        and (AuthorityRow[ValidTo] = null or AuthorityRow[ValidTo] >= CurrentDate)
            ),
        type table
    ),
    WithAuthorityCount = Table.AddColumn(WithAuthority, "AuthorityMatchCount", each Table.RowCount([AuthorityMatch]), Int64.Type),
    SelectedAuthority = Table.SelectRows(WithAuthorityCount, each [AuthorityMatchCount] = 1),
    Result = Table.RemoveColumns(SelectedAuthority, {"AuthorityMatch", "AuthorityMatchCount", "ScheduleAuthority"})
in
    Result
