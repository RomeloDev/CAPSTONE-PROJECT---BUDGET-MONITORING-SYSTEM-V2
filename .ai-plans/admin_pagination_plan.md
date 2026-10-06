# Admin Panel Pagination — Implementation Plan

## Audit Summary Table

| Template                         | View                              | paginate_by set? | Pagination UI? | Filters to Preserve                                                           | Status   |
| -------------------------------- | --------------------------------- | ---------------- | -------------- | ----------------------------------------------------------------------------- | -------- |
| audit_trail.html                 | AuditTrailListView                | Yes (20)         | Yes (custom)   | tab, department, transaction_type, action, start_date, end_date               | Complete |
| approved_budget.html             | ApprovedBudgetListView            | Yes (10)         | Yes (custom)   | summary_year, fiscal_year, amount_min, amount_max, date_from, date_to, search | Complete |
| budget_allocation.html           | BudgetAllocationListView          | Yes (10)         | Yes (custom)   | summary_year, fiscal_year, mfo, department, search                            | Complete |
| pr_list.html                     | AdminPRListView                   | Yes (10)         | Yes (custom)   | summary_year, department, status                                              | Complete |
| departments_ad_request.html      | DepartmentADRequestView           | Yes (10)         | Yes (custom)   | summary_year, department, status                                              | Complete |
| pre_list.html                    | PRERequestListView                | Yes (10)         | Yes (custom)   | search, department, status, date_from, date_to                                | Complete |
| pre_budget_realignment_list.html | AdminPREBudgetRealignmentListView | Yes (10)         | Yes (custom)   | status                                                                        | Complete |

## Gap Analysis Per Pair

### Pair 1: audit_trail.html / AuditTrailListView

- Current state: pagination UI updated to match the reference and preserves `tab` plus filters.
- Required changes to the view (exact code change): none.
- Required changes to the template: none.
- GET parameters to preserve in pagination links: `tab`, `department`, `transaction_type`, `action`, `start_date`, `end_date`.
- Count/length references to update: none.
- Risk/complication notes: two querysets depending on `tab`; keep `tab` in links so pagination does not switch tabs.

### Pair 2: approved_budget.html / ApprovedBudgetListView

- Current state: pagination UI updated to match the reference and preserves all filters.
- Required changes to the view (exact code change): none.
- Required changes to the template: none.
- GET parameters to preserve in pagination links: `summary_year`, `fiscal_year`, `amount_min`, `amount_max`, `date_from`, `date_to`, `search`.
- Count/length references to update: none.
- Risk/complication notes: none.

### Pair 3: budget_allocation.html / BudgetAllocationListView

- Current state: pagination UI updated to match the reference and preserves all filters.
- Required changes to the view (exact code change): none.
- Required changes to the template: none.
- GET parameters to preserve in pagination links: `summary_year`, `fiscal_year`, `mfo`, `department`, `search`.
- Count/length references to update: none.
- Risk/complication notes: none.

### Pair 4: pr_list.html / AdminPRListView

- Current state: pagination UI added to match the reference; `paginate_by = 10` set in the view.
- Required changes to the view (exact code change): none.
- Required changes to the template: none.
- GET parameters to preserve in pagination links: `summary_year`, `department`, `status`.
- Count/length references to update: none.
- Risk/complication notes: none.

### Pair 5: departments_ad_request.html / DepartmentADRequestView

- Current state: pagination added in the view and template, matching the reference and preserving filters.
- Required changes to the view (exact code change): none.
- Required changes to the template: none.
- GET parameters to preserve in pagination links: `summary_year`, `department`, `status`.
- Count/length references to update: none.
- Risk/complication notes: none.

### Pair 6: pre_list.html / PRERequestListView

- Current state: pagination UI updated to match the reference; count badge uses `{{ page_obj.paginator.count }}`; Draft rows removed from the template.
- Required changes to the view (exact code change): none (queryset already excludes Draft).
- Required changes to the template: none.
- GET parameters to preserve in pagination links: `search`, `department`, `status`, `date_from`, `date_to`.
- Count/length references to update: none.
- Risk/complication notes: none.

### Pair 7: pre_budget_realignment_list.html / AdminPREBudgetRealignmentListView

- Current state: pagination UI updated to match the reference and preserves `status`.
- Required changes to the view (exact code change): none.
- Required changes to the template: none.
- GET parameters to preserve in pagination links: `status`.
- Count/length references to update: none.
- Risk/complication notes: none.

## Pairs Already Complete

- pre_budget_realignment_list.html / AdminPREBudgetRealignmentListView
- budget_allocation.html / BudgetAllocationListView
- approved_budget.html / ApprovedBudgetListView
- pre_list.html / PRERequestListView
- audit_trail.html / AuditTrailListView
- pr_list.html / AdminPRListView
- departments_ad_request.html / DepartmentADRequestView
- client_accounts.html / ClientAccountsListView
- archive_center.html / ArchiveCenterView

## Execution Order

Completed in this order:

1. pre_budget_realignment_list.html
2. budget_allocation.html
3. approved_budget.html
4. pre_list.html
5. audit_trail.html
6. pr_list.html
7. departments_ad_request.html

## Estimated Changes Per Pair

- audit_trail.html / AuditTrailListView: View changes 0 lines, Template changes ~30 lines, Risk Low
- approved_budget.html / ApprovedBudgetListView: View changes 0 lines, Template changes ~30 lines, Risk Low
- budget_allocation.html / BudgetAllocationListView: View changes 0 lines, Template changes ~30 lines, Risk Low
- pr_list.html / AdminPRListView: View changes 1 line, Template changes ~30 lines, Risk Low
- departments_ad_request.html / DepartmentADRequestView: View changes 1 line, Template changes ~30 lines, Risk Low
- pre_list.html / PRERequestListView: View changes 0 lines, Template changes ~30 lines, Risk Low
- pre_budget_realignment_list.html / AdminPREBudgetRealignmentListView: View changes 0 lines, Template changes ~30 lines, Risk Low

## Reference

Pagination UI must match `realignment_history.html` exactly.
