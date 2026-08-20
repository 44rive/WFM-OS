# Python in Excel source

Python is used for analytical work that benefits from statistical libraries:
forecasting, backtesting, simulation, schedule experiments, and anomaly
detection.

External data must first enter the workbook through Power Query. Python cells
consume named queries or tables through `xl()` and return candidate results.
Operational decisions use approved/versioned Excel tables, not an unapproved
recalculating Python result.
