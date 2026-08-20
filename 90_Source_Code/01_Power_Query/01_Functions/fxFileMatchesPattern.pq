(FileName as text, FilePattern as text) as logical =>
let
    Name = Text.Lower(FileName),
    Pattern = Text.Lower(Text.Trim(FilePattern)),
    Parts = Text.Split(Pattern, "*"),
    WildcardCount = List.Count(Parts) - 1,
    Result =
        if Pattern = "" or Pattern = "*" or Pattern = "*.*" then true
        else if WildcardCount = 0 then Name = Pattern
        else if WildcardCount = 1 then
            Text.StartsWith(Name, Parts{0}) and Text.EndsWith(Name, Parts{1})
        else error Error.Record(
            "Unsupported file pattern",
            "Use an exact filename or a pattern containing one wildcard (*).",
            [FilePattern = FilePattern]
        )
in
    Result
