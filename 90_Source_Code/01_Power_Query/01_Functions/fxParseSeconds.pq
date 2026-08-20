(InputValue as any, Context as text) as nullable number =>
let
    Parsed =
        if InputValue = null or Text.Trim(Text.From(InputValue)) = "" then 0
        else if Value.Is(InputValue, type number) then Number.From(InputValue)
        else if Value.Is(InputValue, type duration) then Duration.TotalSeconds(Duration.From(InputValue))
        else
            let
                TextValue = Text.Trim(Text.From(InputValue)),
                AsNumber = try Number.FromText(TextValue, "en-US"),
                AsDuration = try Duration.FromText(TextValue)
            in
                if not AsNumber[HasError] then AsNumber[Value]
                else if not AsDuration[HasError] then Duration.TotalSeconds(AsDuration[Value])
                else error Error.Record(
                    "Invalid duration",
                    Context & " could not be converted to seconds.",
                    [Value = TextValue]
                ),
    Result = if Parsed < 0 then error Context & " cannot be negative." else Parsed
in
    Result
