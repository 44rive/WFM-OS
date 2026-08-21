# 90 · Source code

Reviewable source embedded in the Excel application:

```text
01_Power_Query/  ingestion, validation, canonical facts and dimensions
02_DAX/          explicit governed measures
03_Python/       forecasting, backtesting, simulation, and analysis
04_VBA/          controlled workbook actions only
```

Power Query and DAX folders contain machine-readable manifests. The Windows
installer consumes the Power Query manifest and validates the presence of the
DAX/model contracts; a manifest is not proof that its engine objects are
embedded in the released workbook.
