# Python in Excel source

Python is used for analytical work that benefits from statistical libraries:
forecasting, backtesting, simulation, schedule experiments, and anomaly
detection.

External data must first enter the workbook through Power Query. Python cells
consume named queries or tables through `xl()` and return candidate results.
Operational decisions use approved/versioned Excel tables, not an unapproved
recalculating Python result.

`forecast.py`, `capacity.py`, `planning.py`, `supply.py`, `scheduling.py`,
`leave.py`, `roster.py`, `leave_requests.py`, and `swaps.py` are dependency-free
calculation contracts. `excel_adapter.py` is a thin table adapter for Python in
Excel and must not duplicate their formulas.
Install definitions and
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

Schedule design remains anonymous: approved requirements plus
effective shift patterns and rules produce pattern-count candidates. Approved
pattern counts are expanded independently by Power Query into schedule
coverage. Only that approved coverage can produce leave-capacity candidates.
Named work starts only after that approval boundary. `roster.py` expands stable
unit occurrences and applies the documented deterministic eligibility,
availability, skill, contract, fairness, and bounded-repair rules.
`leave_requests.py` recommends full-request decisions against approved interval
capacity and external entitlement snapshots. `swaps.py` simulates consented
bilateral whole-occurrence exchanges and revalidates the complete roster.
Candidates never approve themselves, and publication is performed by Power
Query only after controlled workbook decisions.
