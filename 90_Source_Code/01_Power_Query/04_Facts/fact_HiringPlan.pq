let
    Source = Table.SelectRows(
        stg_HiringPlanVersions,
        each [ApprovedFlag] and [ValidationStatus] = "VALID"
    ),
    Selected = Table.SelectColumns(
        Source,
        {
            "WaveKey", "PlanVersionKey", "ScenarioKey", "PolicyKey", "ActivityKey",
            "RecruitmentStart", "TrainingStart", "NestingStart", "ProficiencyDate", "PlannedHeads",
            "ExpectedPaidFTE", "TimingStatus", "ApprovedAt", "ApprovedBy", "SourceRunKey"
        }
    ),
    Unique = fxAssertUnique(Selected, {"WaveKey"}, "fact_HiringPlan")
in
    Unique
