# Python in Excel source

Python is used for analytical work that benefits from statistical libraries:
forecasting, backtesting, simulation, schedule experiments, and anomaly
detection.

External data must first enter the workbook through Power Query. Python cells
consume named queries or tables through `xl()` and return candidate results.
Operational decisions use approved/versioned Excel tables, not an unapproved
recalculating Python result.

`forecast.py`, `capacity.py`, `planning.py`, and `supply.py` are dependency-free
calculation contracts. `excel_adapter.py` is a thin table adapter for Python in
Excel and must not duplicate their formulas. Install definitions and
entrypoints in `MANIFEST.csv` order because Python cells calculate in workbook
row-major order.

The forecast baseline is daily. Capacity candidates require interval forecast
rows; daily candidates must be shaped and reconciled to an approved interval
profile before capacity publication. Do not treat a daily total as a 30-minute
arrival rate.

The weekly planning chain is explicit: approved daily candidate, governed
intraday allocation, approved scenario, capacity candidate, approved
requirement, paid-supply projection, hiring candidate, then separate hiring and
supply approvals. A hiring plan must be approved before the corresponding
supply plan so Power Query can reconcile cumulative expected paid FTE.
