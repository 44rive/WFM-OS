# DAX source

DAX measures are grouped by domain and embedded in the Power Pivot model.
Worksheet dashboards consume explicit measures only; implicit aggregations are
not part of the governed model.

Each measure must document its numerator, denominator, exclusions, time grain,
and expected reconciliation source.

`service.dax` owns contact-service metrics. `operational_control.dax` owns
schedule, presence, staffing, conformance, and adherence metrics. Do not
duplicate either definition in worksheet formulas.
