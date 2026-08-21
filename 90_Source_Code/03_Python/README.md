# Python in Excel source

Python is used for analytical work that benefits from statistical libraries:
forecasting, backtesting, simulation, schedule experiments, and anomaly
detection.

External data must first enter the workbook through Power Query. Python cells
consume named queries or tables through `xl()` and return candidate results.
Operational decisions use approved/versioned Excel tables, not an unapproved
recalculating Python result.

`forecast.py` and `capacity.py` are dependency-free calculation contracts.
`excel_adapter.py` is a thin table adapter for Python in Excel and must not
duplicate forecast or capacity formulas. Install definitions and entrypoints in
`MANIFEST.csv` order because Python cells calculate in workbook row-major order.

The forecast baseline is daily. Capacity candidates require interval forecast
rows; daily candidates must be shaped and reconciled to an approved interval
profile before capacity publication. Do not treat a daily total as a 30-minute
arrival rate.
