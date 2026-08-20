(RootPath as text, RelativePath as text) as text =>
let
    CleanRoot = Text.TrimEnd(Text.Trim(RootPath), {"\", "/"}),
    CleanRelative = Text.TrimStart(Text.Trim(RelativePath), {"\", "/"}),
    Result = CleanRoot & "\" & Text.Replace(CleanRelative, "/", "\")
in
    Result
