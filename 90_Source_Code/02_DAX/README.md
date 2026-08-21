# DAX source

DAX measures are grouped by domain and embedded in the Power Pivot model.
Worksheet dashboards consume explicit measures only; implicit aggregations are
not part of the governed model.

Each measure must document its numerator, denominator, exclusions, time grain,
and expected reconciliation source.

`service.dax` owns contact-service metrics. `operational_control.dax` owns
schedule, presence, staffing, conformance, and adherence metrics. Do not
duplicate either definition in worksheet formulas.

`planning.dax` owns approved forecast totals, workload, and forecast-accuracy
measures. Signed forecast error is forecast minus actual, so positive bias means
over-forecast. Capacity algorithms remain in Python; DAX reports their approved
staffing-requirement results through the existing operational measures.

Use `MANIFEST.csv` as the installation contract for measure order, home table,
format, display folder, and business description. Use `RELATIONSHIPS.csv` as
the canonical relationship contract; fact columns are foreign keys and
dimension columns are lookup keys. These CSV files are source metadata, not a
claim that the committed shell already contains a Data Model.
