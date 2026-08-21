(StartA as nullable datetime, EndA as nullable datetime, StartB as nullable datetime, EndB as nullable datetime) as number =>
let
    Result =
        if StartA = null or EndA = null or StartB = null or EndB = null then 0
        else List.Max({
            0,
            Duration.TotalSeconds(List.Min({EndA, EndB}) - List.Max({StartA, StartB}))
        })
in
    Result
