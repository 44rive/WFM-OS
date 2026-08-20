(FolderPath as text, FilePattern as text, DelimiterName as text, EncodingNumber as number) as table =>
let
    Delimiter =
        if Text.Lower(DelimiterName) = "tab" then "#(tab)"
        else if Text.Lower(DelimiterName) = "semicolon" then ";"
        else if Text.Lower(DelimiterName) = "pipe" then "|"
        else ",",
    Files = Folder.Files(FolderPath),
    Visible = Table.SelectRows(
        Files,
        each [Attributes]?[Hidden]? <> true
            and fxFileMatchesPattern([Name], FilePattern)
    ),
    WithRows = Table.AddColumn(
        Visible,
        "Rows",
        (FileRecord as record) as table =>
            let
                Parsed = Csv.Document(
                    FileRecord[Content],
                    [
                        Delimiter = Delimiter,
                        Encoding = Int64.From(EncodingNumber),
                        QuoteStyle = QuoteStyle.Csv
                    ]
                ),
                Promoted = Table.PromoteHeaders(Parsed, [PromoteAllScalars = true]),
                WithFile = Table.AddColumn(
                    Promoted,
                    "SourceFile",
                    each FileRecord[Name],
                    type text
                ),
                WithModified = Table.AddColumn(
                    WithFile,
                    "SourceModifiedAt",
                    each FileRecord[Date modified],
                    type datetime
                )
            in
                WithModified,
        type table
    ),
    Result =
        if Table.RowCount(WithRows) = 0 then
            error Error.Record(
                "No source files",
                "No files matching " & FilePattern & " were found in " & FolderPath & ".",
                [FolderPath = FolderPath, FilePattern = FilePattern]
            )
        else Table.Combine(WithRows[Rows])
in
    Result
