let
    Source = src_Contacts,
    QueueSource = Excel.CurrentWorkbook(){[Name = "tblQueueMapping"]}[Content],
    QueueContract = fxAssertColumns(
        QueueSource,
        {
            "Profile", "SystemKey", "SourceQueueID", "QueueKey", "QueueName",
            "ActivityKey", "ChannelKey", "ValidFrom", "ValidTo", "Enabled"
        },
        "tblQueueMapping"
    ),
    TypedQueues = Table.TransformColumnTypes(
        QueueContract,
        {
            {"SystemKey", type text}, {"SourceQueueID", type text},
            {"ValidFrom", type date}, {"ValidTo", type nullable date}
        }
    ),
    ActiveQueues = Table.SelectRows(
        TypedQueues,
        each Text.From([Profile]) = p_Profile and fxAsLogical([Enabled])
    ),
    WithBusinessDate = Table.AddColumn(
        Source,
        "BusinessDate",
        each Date.From([ContactStart]),
        type date
    ),
    WithQueueMatches = Table.AddColumn(
        WithBusinessDate,
        "QueueMatches",
        (ContactRow as record) as table => Table.SelectRows(
            ActiveQueues,
            (QueueRow as record) as logical =>
                QueueRow[SystemKey] = ContactRow[SystemKey]
                    and QueueRow[SourceQueueID] = ContactRow[QueueExternalID]
                    and QueueRow[ValidFrom] <= ContactRow[BusinessDate]
                    and (QueueRow[ValidTo] = null or QueueRow[ValidTo] >= ContactRow[BusinessDate])
        ),
        type table
    ),
    WithQueueMatchCount = Table.AddColumn(
        WithQueueMatches,
        "QueueMatchCount",
        each Table.RowCount([QueueMatches]),
        Int64.Type
    ),
    WithQueueRecord = Table.AddColumn(
        WithQueueMatchCount,
        "QueueMapping",
        each if [QueueMatchCount] = 1 then [QueueMatches]{0} else null,
        type nullable record
    ),
    WithoutMatchTables = Table.RemoveColumns(WithQueueRecord, {"QueueMatches"}),
    Expanded = Table.ExpandRecordColumn(
        WithoutMatchTables,
        "QueueMapping",
        {"QueueKey", "QueueName", "ActivityKey", "ChannelKey", "ValidFrom", "ValidTo"},
        {"QueueKey", "QueueName", "ActivityKey", "ChannelKey", "QueueValidFrom", "QueueValidTo"}
    ),
    WithMappingStatus = Table.AddColumn(
        Expanded,
        "MappingStatus",
        each
            if [QueueMatchCount] = 0 then "Unmapped queue or validity gap"
            else if [QueueMatchCount] > 1 then "Ambiguous queue mapping"
            else if [Direction] = null then "Unmapped direction"
            else if [Outcome] = null then "Unmapped outcome"
            else "Mapped",
        type text
    ),
    WithMappingValue = Table.AddColumn(
        WithMappingStatus,
        "MappingValue",
        each
            if [QueueMatchCount] <> 1 then [SystemKey] & "|" & [QueueExternalID]
            else if [Direction] = null then [SystemKey] & "|" & [SourceDirection]
            else if [Outcome] = null then [SystemKey] & "|" & [SourceOutcome]
            else null,
        type nullable text
    ),
    WithIntervalKey = Table.AddColumn(
        WithMappingValue,
        "IntervalKey",
        each "I" & Text.PadStart(
            Text.From(Time.Hour(Time.From([ContactStart])) * 2
                + (if Time.Minute(Time.From([ContactStart])) >= 30 then 1 else 0)),
            2,
            "0"
        ),
        type text
    ),
    WithAgentKey = Table.AddColumn(
        WithIntervalKey,
        "AgentKey",
        each
            if [AgentExternalID] = null or Text.Trim([AgentExternalID]) = "" then null
            else [SystemKey] & "|" & [AgentExternalID],
        type nullable text
    ),
    WithOffered = Table.AddColumn(
        WithAgentKey,
        "Offered",
        each if [Direction] = "Inbound" then 1 else 0,
        Int64.Type
    ),
    WithHandled = Table.AddColumn(
        WithOffered,
        "Handled",
        each if [Offered] = 1 and [Outcome] = "Handled" then 1 else 0,
        Int64.Type
    ),
    WithShortAbandon = Table.AddColumn(
        WithHandled,
        "ShortAbandon",
        each
            if [Offered] = 1 and [Outcome] = "Abandoned"
                and [WaitSeconds] < Number.From(p_ShortAbandonThresholdSeconds)
            then 1 else 0,
        Int64.Type
    ),
    WithEligibleOffered = Table.AddColumn(
        WithShortAbandon,
        "SLEligibleOffered",
        each
            if [Offered] = 1
                and (not fxAsLogical(p_ExcludeShortAbandons) or [ShortAbandon] = 0)
            then 1 else 0,
        Int64.Type
    ),
    WithAnsweredWithinSL = Table.AddColumn(
        WithEligibleOffered,
        "AnsweredWithinSL",
        each
            if [Handled] = 1 and [WaitSeconds] <= Number.From(p_SLThresholdSeconds)
            then 1 else 0,
        Int64.Type
    ),
    WithHandleSeconds = Table.AddColumn(
        WithAnsweredWithinSL,
        "HandleSeconds",
        each
            if [Handled] = 1 then
                [TalkSeconds] + [HoldSeconds] + [AfterContactSeconds]
            else 0,
        type number
    )
in
    WithHandleSeconds
