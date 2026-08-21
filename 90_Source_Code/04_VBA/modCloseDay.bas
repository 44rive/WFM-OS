Attribute VB_Name = "modCloseDay"
Option Explicit

' Controlled close-day publisher for the future .xlsm release.
' Business logic stays in Power Query and DAX; this module only validates and
' copies one approved, reconciled snapshot candidate into the append-only store.

Private Const CLOSE_INPUT_TABLE As String = "tblCloseDayInput"
Private Const READY_TABLE As String = "tblCloseDayReady"
Private Const SNAPSHOT_TABLE As String = "tblOperationalSnapshots"
Private Const DQ_TABLE As String = "tblDQChecks"

Public Sub CloseOperationalDay()
    Dim closeTable As ListObject
    Dim readyTable As ListObject
    Dim snapshotTable As ListObject
    Dim closeRow As ListRow
    Dim businessDate As Date
    Dim profile As String
    Dim sourceRunKey As String
    Dim readyCount As Long
    Dim existingCount As Long
    Dim closedAt As Date

    On Error GoTo Fail
    Application.ScreenUpdating = False
    Application.EnableEvents = False

    Set closeTable = FindTable(CLOSE_INPUT_TABLE)
    Set readyTable = FindTable(READY_TABLE)
    Set snapshotTable = FindTable(SNAPSHOT_TABLE)

    If HasBlockingDataQuality() Then
        Err.Raise vbObjectError + 2100, , "Close day is blocked by Data Quality."
    End If

    Set closeRow = ApprovedCloseRow(closeTable)
    If closeRow Is Nothing Then
        Err.Raise vbObjectError + 2101, , "Exactly one approved close-day request is required."
    End If

    profile = Trim$(CStr(RowValue(closeTable, closeRow, "Profile")))
    businessDate = DateValue(RowValue(closeTable, closeRow, "BusinessDate"))
    sourceRunKey = Trim$(CStr(RowValue(closeTable, closeRow, "SourceRunKey")))
    If Len(profile) = 0 Or Len(sourceRunKey) = 0 Then
        Err.Raise vbObjectError + 2102, , "Profile and SourceRunKey are required."
    End If

    readyCount = ValidateReadyRows(readyTable, profile, businessDate)
    If readyCount = 0 Then
        Err.Raise vbObjectError + 2103, , "The approved date has no reconciled snapshot rows."
    End If

    existingCount = ExistingFinalCount(snapshotTable, readyTable, profile, businessDate)
    If existingCount = readyCount Then
        MarkRequestClosed closeTable, closeRow, Now
        MsgBox "This business date is already closed with the same snapshot keys.", vbInformation, "WFM OS"
        GoTo CleanExit
    ElseIf existingCount <> 0 Then
        Err.Raise vbObjectError + 2104, , "A partial or conflicting final snapshot already exists."
    End If

    DeleteProvisionalRows snapshotTable, profile, businessDate
    closedAt = Now
    AppendReadyRows readyTable, snapshotTable, profile, businessDate, closedAt, Application.UserName, sourceRunKey
    MarkRequestClosed closeTable, closeRow, closedAt

    MsgBox CStr(readyCount) & " interval snapshots were finalized.", vbInformation, "WFM OS"

CleanExit:
    Application.EnableEvents = True
    Application.ScreenUpdating = True
    Exit Sub

Fail:
    Application.EnableEvents = True
    Application.ScreenUpdating = True
    MsgBox Err.Description, vbCritical, "WFM OS · Close day blocked"
End Sub

Private Function FindTable(ByVal tableName As String) As ListObject
    Dim sheet As Worksheet
    Dim candidate As ListObject
    For Each sheet In ThisWorkbook.Worksheets
        For Each candidate In sheet.ListObjects
            If StrComp(candidate.Name, tableName, vbTextCompare) = 0 Then
                Set FindTable = candidate
                Exit Function
            End If
        Next candidate
    Next sheet
    Err.Raise vbObjectError + 2110, , "Required table is missing: " & tableName
End Function

Private Function RowValue(ByVal table As ListObject, ByVal row As ListRow, ByVal columnName As String) As Variant
    RowValue = row.Range.Cells(1, table.ListColumns(columnName).Index).Value2
End Function

Private Sub SetRowValue(ByVal table As ListObject, ByVal row As ListRow, ByVal columnName As String, ByVal value As Variant)
    row.Range.Cells(1, table.ListColumns(columnName).Index).Value = value
End Sub

Private Function HasBlockingDataQuality() As Boolean
    Dim table As ListObject
    Dim row As ListRow
    Dim status As String
    Set table = FindTable(DQ_TABLE)
    For Each row In table.ListRows
        status = UCase$(Trim$(CStr(RowValue(table, row, "Status"))))
        If status <> "PASSED" And status <> "WARNING" Then
            HasBlockingDataQuality = True
            Exit Function
        End If
    Next row
End Function

Private Function ApprovedCloseRow(ByVal table As ListObject) As ListRow
    Dim row As ListRow
    Dim approvedCount As Long
    For Each row In table.ListRows
        If UCase$(Trim$(CStr(RowValue(table, row, "ApprovalStatus")))) = "APPROVED" _
            And UCase$(Trim$(CStr(RowValue(table, row, "SnapshotStatus")))) <> "FINAL" Then
            approvedCount = approvedCount + 1
            Set ApprovedCloseRow = row
        End If
    Next row
    If approvedCount <> 1 Then Set ApprovedCloseRow = Nothing
End Function

Private Function ValidateReadyRows(ByVal table As ListObject, ByVal profile As String, ByVal businessDate As Date) As Long
    Dim row As ListRow
    Dim seen As Object
    Dim snapshotKey As String
    Set seen = CreateObject("Scripting.Dictionary")

    For Each row In table.ListRows
        If RowMatchesScope(table, row, profile, businessDate) Then
            snapshotKey = Trim$(CStr(RowValue(table, row, "SnapshotKey")))
            If Len(snapshotKey) = 0 Then Err.Raise vbObjectError + 2120, , "SnapshotKey cannot be blank."
            If seen.Exists(snapshotKey) Then Err.Raise vbObjectError + 2121, , "Duplicate snapshot key: " & snapshotKey
            If Len(Trim$(CStr(RowValue(table, row, "RequiredFTE")))) = 0 Then Err.Raise vbObjectError + 2122, , "RequiredFTE cannot be blank."
            seen.Add snapshotKey, True
        End If
    Next row
    ValidateReadyRows = seen.Count
End Function

Private Function ExistingFinalCount(ByVal destination As ListObject, ByVal ready As ListObject, ByVal profile As String, ByVal businessDate As Date) As Long
    Dim row As ListRow
    Dim readyKeys As Object
    Set readyKeys = CreateObject("Scripting.Dictionary")
    For Each row In ready.ListRows
        If RowMatchesScope(ready, row, profile, businessDate) Then
            readyKeys(Trim$(CStr(RowValue(ready, row, "SnapshotKey")))) = True
        End If
    Next row
    For Each row In destination.ListRows
        If RowMatchesScope(destination, row, profile, businessDate) Then
            If UCase$(Trim$(CStr(RowValue(destination, row, "Status")))) = "FINAL" Then
                If Not readyKeys.Exists(Trim$(CStr(RowValue(destination, row, "SnapshotKey")))) Then
                    ExistingFinalCount = -1
                    Exit Function
                End If
                ExistingFinalCount = ExistingFinalCount + 1
            End If
        End If
    Next row
End Function

Private Sub DeleteProvisionalRows(ByVal table As ListObject, ByVal profile As String, ByVal businessDate As Date)
    Dim index As Long
    For index = table.ListRows.Count To 1 Step -1
        If RowMatchesScope(table, table.ListRows(index), profile, businessDate) Then
            If UCase$(Trim$(CStr(RowValue(table, table.ListRows(index), "Status")))) = "PROVISIONAL" Then
                table.ListRows(index).Delete
            End If
        End If
    Next index
End Sub

Private Sub AppendReadyRows(ByVal source As ListObject, ByVal destination As ListObject, ByVal profile As String, ByVal businessDate As Date, ByVal closedAt As Date, ByVal closedBy As String, ByVal sourceRunKey As String)
    Dim sourceRow As ListRow
    Dim destinationRow As ListRow
    Dim field As Variant
    Dim fields As Variant
    fields = Array("SnapshotKey", "Profile", "BusinessDate", "IntervalStart", "ActivityKey", _
        "ScheduledFTE", "ScheduledProductiveFTE", "PresentFTE", "ProductiveFTE", _
        "RequiredFTE", "NetProductiveFTE")

    For Each sourceRow In source.ListRows
        If RowMatchesScope(source, sourceRow, profile, businessDate) Then
            Set destinationRow = destination.ListRows.Add
            For Each field In fields
                SetRowValue destination, destinationRow, CStr(field), RowValue(source, sourceRow, CStr(field))
            Next field
            SetRowValue destination, destinationRow, "Status", "FINAL"
            SetRowValue destination, destinationRow, "ClosedAt", closedAt
            SetRowValue destination, destinationRow, "ClosedBy", closedBy
            SetRowValue destination, destinationRow, "SourceRunKey", sourceRunKey
        End If
    Next sourceRow
End Sub

Private Function RowMatchesScope(ByVal table As ListObject, ByVal row As ListRow, ByVal profile As String, ByVal businessDate As Date) As Boolean
    If Trim$(CStr(RowValue(table, row, "Profile"))) <> profile Then Exit Function
    If Not IsDate(RowValue(table, row, "BusinessDate")) Then Exit Function
    RowMatchesScope = (DateValue(RowValue(table, row, "BusinessDate")) = businessDate)
End Function

Private Sub MarkRequestClosed(ByVal table As ListObject, ByVal row As ListRow, ByVal closedAt As Date)
    SetRowValue table, row, "SnapshotStatus", "FINAL"
    SetRowValue table, row, "SnapshotAt", closedAt
End Sub
