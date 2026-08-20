# ADR 0001: Modular Excel monolith

## Status

Accepted.

## Context

The application must remain understandable, portable, and operable by a WFM
lead using Excel, while avoiding duplicated workbook logic and broken links.

## Decision

Use one primary `.xlsm` workbook containing the user experience, Power Query,
Power Pivot, DAX, Python-in-Excel analysis, configuration, and audit controls.
Keep raw data, generated outputs, and backups external to the workbook.

## Consequences

- One metric model and refresh surface improve consistency and portability.
- A single named owner and controlled publishing process are required.
- The workbook is not intended for unrestricted concurrent editing.
- Restricted compensation data may require a separate deployment module.
- If scale or concurrency outgrows Excel, the canonical contracts remain the
  migration boundary.
