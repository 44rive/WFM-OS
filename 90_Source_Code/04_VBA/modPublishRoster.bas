Attribute VB_Name = "modPublishRoster"
Option Explicit

' Controlled roster publisher for the future reviewed .xlsm release.
' It exports only pseudonymous published interval rows. Power Query owns roster
' construction; this module owns the timestamped file action and append-only log.

Private Const PUBLICATION_TABLE As String = "tblRosterPublications"
Private Const OUTPUT_TABLE As String = "out_PublishedRosterSegments"
Private Const PUBLICATION_DQ_TABLE As String = "dq_RosterPublication"
Private Const LOG_TABLE As String = "tblRosterPublicationLog"
Private Const PARAMETER_TABLE As String = "tblParameters"

Public Sub PublishApprovedRoster()
    Dim publicationTable As ListObject
    Dim outputTable As ListObject
    Dim logTable As ListObject
    Dim publicationRow As ListRow
    Dim publicationVersion As String
    Dim rosterVersion As String
    Dim publishedAt As Date
    Dim publishedBy As String
    Dim outputRoot As String
    Dim outputPath As String
    Dim rowCount As Long

    On Error GoTo Fail
    Application.ScreenUpdating = False
    Application.EnableEvents = False

    Set publicationTable = FindRosterTable(PUBLICATION_TABLE)
    Set logTable = FindRosterTable(LOG_TABLE)
    Set publicationRow = PendingApprovedPublication(publicationTable)
    If publicationRow Is Nothing Then
        Err.Raise vbObjectError + 2300, , "Exactly one approved, unpublished roster publication is required."
    End If

    publicationVersion = Trim$(CStr(RosterRowValue(publicationTable, publicationRow, "PublicationVersionKey")))
    rosterVersion = Trim$(CStr(RosterRowValue(publicationTable, publicationRow, "RosterVersionKey")))
    If Len(publicationVersion) = 0 Or Len(rosterVersion) = 0 Then
        Err.Raise vbObjectError + 2301, , "PublicationVersionKey and RosterVersionKey are required."
    End If
    If PublicationAlreadyLogged(logTable, publicationVersion) Then
        Err.Raise vbObjectError + 2302, , "This publication version already has an append-only log row."
    End If

    outputRoot = RosterParameterValue("RosterPublicationRoot")
    If Len(outputRoot) = 0 Or InStr(1, outputRoot, "<SET", vbTextCompare) > 0 Then
        Err.Raise vbObjectError + 2303, , "RosterPublicationRoot must be configured to a restricted absolute folder."
    End If
    If Dir$(outputRoot, vbDirectory) = vbNullString Then
        Err.Raise vbObjectError + 2304, , "RosterPublicationRoot does not exist."
    End If

    publishedAt = Now
    publishedBy = Application.UserName
    RosterSetRowValue publicationTable, publicationRow, "PublishedAt", publishedAt
    RosterSetRowValue publicationTable, publicationRow, "PublishedBy", publishedBy

    ThisWorkbook.RefreshAll
    Application.CalculateUntilAsyncQueriesDone
    If HasRosterPublicationIssues() Then
        Err.Raise vbObjectError + 2305, , "Publication is blocked by dq_RosterPublication."
    End If

    Set outputTable = FindRosterTable(OUTPUT_TABLE)
    rowCount = ValidatePublishedRows(outputTable, publicationVersion, rosterVersion)
    If rowCount = 0 Then
        Err.Raise vbObjectError + 2306, , "The approved publication produced no interval rows."
    End If

    outputPath = CombineRosterPath(outputRoot, SafeRosterFileName(publicationVersion) & ".csv")
    If Len(Dir$(outputPath)) > 0 Then
        Err.Raise vbObjectError + 2307, , "The target publication file already exists."
    End If
    ExportRosterCsv outputTable, publicationVersion, outputPath
    AppendPublicationLog logTable, publicationTable, publicationRow, outputPath, rowCount, publishedAt, publishedBy

    MsgBox CStr(rowCount) & " pseudonymous roster interval rows were exported." & vbCrLf & _
        "Complete the external SHA-256 evidence before release.", vbInformation, "WFM OS"

CleanExit:
    Application.EnableEvents = True
    Application.ScreenUpdating = True
    Exit Sub

Fail:
    On Error Resume Next
    If Not publicationRow Is Nothing Then
        RosterSetRowValue publicationTable, publicationRow, "PublishedAt", Empty
        RosterSetRowValue publicationTable, publicationRow, "PublishedBy", Empty
    End If
    Application.EnableEvents = True
    Application.ScreenUpdating = True
    MsgBox Err.Description, vbCritical, "WFM OS · Roster publication blocked"
End Sub

Private Function FindRosterTable(ByVal tableName As String) As ListObject
    Dim sheet As Worksheet
    Dim candidate As ListObject
    For Each sheet In ThisWorkbook.Worksheets
        For Each candidate In sheet.ListObjects
            If StrComp(candidate.Name, tableName, vbTextCompare) = 0 Then
                Set FindRosterTable = candidate
                Exit Function
            End If
        Next candidate
    Next sheet
    Err.Raise vbObjectError + 2310, , "Required table is missing: " & tableName
End Function

Private Function RosterRowValue(ByVal table As ListObject, ByVal row As ListRow, ByVal columnName As String) As Variant
    RosterRowValue = row.Range.Cells(1, table.ListColumns(columnName).Index).Value2
End Function

Private Sub RosterSetRowValue(ByVal table As ListObject, ByVal row As ListRow, ByVal columnName As String, ByVal value As Variant)
    row.Range.Cells(1, table.ListColumns(columnName).Index).Value = value
End Sub

Private Function PendingApprovedPublication(ByVal table As ListObject) As ListRow
    Dim row As ListRow
    Dim matchCount As Long
    For Each row In table.ListRows
        If UCase$(Trim$(CStr(RosterRowValue(table, row, "ApprovalStatus")))) = "APPROVED" _
            And Len(Trim$(CStr(RosterRowValue(table, row, "PublishedAt")))) = 0 Then
            matchCount = matchCount + 1
            Set PendingApprovedPublication = row
        End If
    Next row
    If matchCount <> 1 Then Set PendingApprovedPublication = Nothing
End Function

Private Function PublicationAlreadyLogged(ByVal table As ListObject, ByVal publicationVersion As String) As Boolean
    Dim row As ListRow
    For Each row In table.ListRows
        If Trim$(CStr(RosterRowValue(table, row, "PublicationVersionKey"))) = publicationVersion Then
            PublicationAlreadyLogged = True
            Exit Function
        End If
    Next row
End Function

Private Function RosterParameterValue(ByVal parameterName As String) As String
    Dim table As ListObject
    Dim row As ListRow
    Set table = FindRosterTable(PARAMETER_TABLE)
    For Each row In table.ListRows
        If Trim$(CStr(RosterRowValue(table, row, "Parameter"))) = parameterName Then
            RosterParameterValue = Trim$(CStr(RosterRowValue(table, row, "Value")))
            Exit Function
        End If
    Next row
    Err.Raise vbObjectError + 2311, , "Required parameter is missing: " & parameterName
End Function

Private Function HasRosterPublicationIssues() As Boolean
    Dim table As ListObject
    Dim row As ListRow
    Set table = FindRosterTable(PUBLICATION_DQ_TABLE)
    For Each row In table.ListRows
        If UCase$(Trim$(CStr(RosterRowValue(table, row, "Severity")))) = "BLOCKING" Then
            HasRosterPublicationIssues = True
            Exit Function
        End If
    Next row
End Function

Private Function ValidatePublishedRows(ByVal table As ListObject, ByVal publicationVersion As String, ByVal rosterVersion As String) As Long
    Dim row As ListRow
    Dim segmentKey As String
    Dim seen As Object
    Set seen = CreateObject("Scripting.Dictionary")
    If HasRosterColumn(table, "DisplayName") Or HasRosterColumn(table, "EmployeeBusinessID") Then
        Err.Raise vbObjectError + 2320, , "Published roster output contains a forbidden identity column."
    End If
    For Each row In table.ListRows
        If Trim$(CStr(RosterRowValue(table, row, "PublicationVersionKey"))) = publicationVersion Then
            If Trim$(CStr(RosterRowValue(table, row, "RosterVersionKey"))) <> rosterVersion Then
                Err.Raise vbObjectError + 2321, , "Published roster lineage does not match the approved roster."
            End If
            If Len(Trim$(CStr(RosterRowValue(table, row, "AgentKey")))) = 0 Then
                Err.Raise vbObjectError + 2322, , "Published AgentKey cannot be blank."
            End If
            segmentKey = Trim$(CStr(RosterRowValue(table, row, "SegmentKey")))
            If Len(segmentKey) = 0 Or seen.Exists(segmentKey) Then
                Err.Raise vbObjectError + 2323, , "Published segment keys must be nonblank and unique."
            End If
            seen.Add segmentKey, True
        End If
    Next row
    ValidatePublishedRows = seen.Count
End Function

Private Function HasRosterColumn(ByVal table As ListObject, ByVal columnName As String) As Boolean
    Dim column As ListColumn
    For Each column In table.ListColumns
        If StrComp(column.Name, columnName, vbTextCompare) = 0 Then
            HasRosterColumn = True
            Exit Function
        End If
    Next column
End Function

Private Sub ExportRosterCsv(ByVal table As ListObject, ByVal publicationVersion As String, ByVal outputPath As String)
    Dim stream As Object
    Dim row As ListRow
    Dim fields As Variant
    Dim field As Variant
    Dim line As String
    fields = Array("PublicationVersionKey", "RosterVersionKey", "OccurrenceKey", "SegmentKey", _
        "BusinessDate", "IntervalStart", "IntervalKey", "AgentKey", "ActivityKey", _
        "ScheduleTypeKey", "PaidFlag", "ProductiveFlag", "ScheduledSeconds", "PublicationStatus")
    Set stream = CreateObject("ADODB.Stream")
    stream.Type = 2
    stream.Charset = "utf-8"
    stream.Open
    For Each field In fields
        If Len(line) > 0 Then line = line & ","
        line = line & CsvRosterValue(CStr(field))
    Next field
    stream.WriteText line & vbCrLf
    For Each row In table.ListRows
        If Trim$(CStr(RosterRowValue(table, row, "PublicationVersionKey"))) = publicationVersion Then
            line = vbNullString
            For Each field In fields
                If Len(line) > 0 Then line = line & ","
                line = line & CsvRosterValue(RosterRowValue(table, row, CStr(field)))
            Next field
            stream.WriteText line & vbCrLf
        End If
    Next row
    stream.SaveToFile outputPath, 2
    stream.Close
End Sub

Private Function CsvRosterValue(ByVal value As Variant) As String
    Dim text As String
    text = CStr(value)
    CsvRosterValue = """" & Replace(text, """", """""") & """"
End Function

Private Sub AppendPublicationLog(ByVal logTable As ListObject, ByVal publicationTable As ListObject, ByVal publicationRow As ListRow, ByVal outputPath As String, ByVal rowCount As Long, ByVal publishedAt As Date, ByVal publishedBy As String)
    Dim row As ListRow
    Dim publicationVersion As String
    publicationVersion = Trim$(CStr(RosterRowValue(publicationTable, publicationRow, "PublicationVersionKey")))
    Set row = logTable.ListRows.Add
    RosterSetRowValue logTable, row, "PublicationLogKey", publicationVersion & "|" & Format$(publishedAt, "yyyymmddhhnnss")
    RosterSetRowValue logTable, row, "PublicationKey", RosterRowValue(publicationTable, publicationRow, "PublicationKey")
    RosterSetRowValue logTable, row, "Profile", RosterRowValue(publicationTable, publicationRow, "Profile")
    RosterSetRowValue logTable, row, "PublicationVersionKey", publicationVersion
    RosterSetRowValue logTable, row, "RosterVersionKey", RosterRowValue(publicationTable, publicationRow, "RosterVersionKey")
    RosterSetRowValue logTable, row, "PublishedAt", publishedAt
    RosterSetRowValue logTable, row, "PublishedBy", publishedBy
    RosterSetRowValue logTable, row, "OutputPath", outputPath
    RosterSetRowValue logTable, row, "RowCount", rowCount
    RosterSetRowValue logTable, row, "ContentHash", ""
    RosterSetRowValue logTable, row, "Status", "EXPORTED_HASH_REQUIRED"
End Sub

Private Function SafeRosterFileName(ByVal value As String) As String
    Dim forbidden As Variant
    For Each forbidden In Array("\", "/", ":", "*", "?", """", "<", ">", "|")
        value = Replace(value, CStr(forbidden), "_")
    Next forbidden
    SafeRosterFileName = value
End Function

Private Function CombineRosterPath(ByVal folder As String, ByVal fileName As String) As String
    If Right$(folder, 1) = "\" Or Right$(folder, 1) = "/" Then
        CombineRosterPath = folder & fileName
    Else
        CombineRosterPath = folder & Application.PathSeparator & fileName
    End If
End Function
