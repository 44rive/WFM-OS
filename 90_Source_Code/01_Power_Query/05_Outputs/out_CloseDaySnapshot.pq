let
    Source = Table.SelectRows(out_IntervalStaffing, each [BusinessDate] = p_AsOfDate),
    WithProfile = Table.AddColumn(Source, "Profile", each p_Profile, type text),
    WithSnapshotKey = Table.AddColumn(
        WithProfile,
        "SnapshotKey",
        each p_Profile & "|" & Date.ToText([BusinessDate], "yyyyMMdd") & "|"
            & DateTime.ToText([IntervalStart], "HHmm") & "|" & [ActivityKey],
        type text
    ),
    WithStatus = Table.AddColumn(WithSnapshotKey, "Status", each "PROVISIONAL", type text),
    Result = Table.SelectColumns(
        WithStatus,
        {
            "SnapshotKey", "Profile", "BusinessDate", "IntervalStart", "ActivityKey",
            "ScheduledFTE", "ScheduledProductiveFTE", "PresentFTE", "ProductiveFTE",
            "RequiredFTE", "NetProductiveFTE", "Status"
        }
    )
in
    Result
