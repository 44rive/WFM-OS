# Repository working rules

- Read `AI_GUIDE.md` completely before changing the workbook, configuration,
  canonical contracts, Power Query, DAX, Python, VBA, or design system.
- Treat this as an Excel application, not a collection of spreadsheet templates.
- Preserve vendor neutrality below the adapter layer.
- Keep Power Query, DAX, Python, and VBA source synchronized with the workbook.
- Do not commit production data or inferred employee information.
- Use anonymized fixtures for every validation and example.
- Do not silently discard unknown source values; surface them in data quality.
- Prefer a small number of reusable M functions over repeated query code.
- Prefer explicit DAX measures over worksheet formula grids.
- Follow `00_Governance/00-03_DESIGN_SYSTEM.md`; do not improvise new colors or
  components.
- Record architectural changes in `00_Governance/00-05_Decisions/`.
- Keep `tools/windows/installer-contract.json`, the query/DAX/relationship
  manifests, and `91_Tests/test_excel_installer_contract.py` aligned. Never
  convert a `MANUAL_REQUIRED` engine step into an automated claim without a
  successful desktop Excel fixture run and evidence.
