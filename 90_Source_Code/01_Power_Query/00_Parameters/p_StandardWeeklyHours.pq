let
    Value = Number.From(fxGetParameter("StandardWeeklyHours", 40)),
    Result = if Value <= 0 then error "StandardWeeklyHours must be greater than zero" else Value
in
    Result
