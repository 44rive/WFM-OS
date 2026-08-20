(InputValue as any) as logical =>
let
    Result =
        if Value.Is(InputValue, type logical) then InputValue
        else List.Contains(
            {"TRUE", "1", "YES", "Y"},
            Text.Upper(Text.Trim(Text.From(InputValue)))
        )
in
    Result
