# VIEWS

---

## App: `budgets` (AJAX Endpoints)

### `convert_document_to_pdf` (function)
- **URL:** `budgets/api/convert-to-pdf/` → `name='convert_to_pdf'`
- **Methods:** POST only (`@require_POST`)
- **Auth:** `@login_required`
- **Request format (JSON body):**
  ```json
  { "document_id": "string", "document_type": "string" }
  ```
- **Response format:**
  ```json
  { "success": true, "pdf_url": "/media/..." }
  { "success": false, "error": "..." }
  ```
- **Logic:** Looks up `document_type` in `DOCUMENT_TYPE_MAP` whitelist → fetches model instance → returns existing converted PDF or runs LibreOffice conversion
- **DOCUMENT_TYPE_MAP whitelist:**

| Key | Model | Source Field | PDF Field | PK Type |
|-----|-------|-------------|-----------|---------|
| `pre_supporting_doc` | DepartmentPRESupportingDocument | `document` | `converted_pdf` | int |
| `pr_supporting_doc` | PurchaseRequestSupportingDocument | `document` | `converted_pdf` | int |
| `ad_supporting_doc` | ActivityDesignSupportingDocument | `document` | `converted_pdf` | int |
| `br_supporting_doc` | BudgetRealignmentSupportingDocument | `document` | `converted_pdf` | int |
| `pr_approved_doc` | PurchaseRequestApprovedDocument | `document` | `converted_pdf` | int |
| `ad_approved_doc` | ActivityDesignApprovedDocument | `document` | `converted_pdf` | int |
| `ab_supporting_doc` | SupportingDocument | `document` | `converted_pdf` | int |
| `pre_main` | DepartmentPRE | `uploaded_excel_file` | `uploaded_excel_pdf` | UUID |
| `pr_main` | PurchaseRequest | `uploaded_document` | `uploaded_document_pdf` | UUID |
| `ad_main` | ActivityDesign | `uploaded_document` | `uploaded_document_pdf` | UUID |

---

## App: `admin_panel`

All admin views require `is_staff=True` (enforced via `UserPassesTestMixin` with `test_func` checking `request.user.is_staff`).

### Class-Based Views

| View | Type | URL | Template | Purpose |
|------|------|-----|----------|---------|
| `AdminDashboardView` | TemplateView | `admin-panel/dashboard/` | `dashboard.html` | Admin dashboard with summary stats |
| `ApprovedBudgetListView` | ListView | `admin-panel/approved_budget/` | `approved_budget.html` | List all approved budgets |
| `BudgetAllocationListView` | ListView | `admin-panel/budget_allocation/` | `budget_allocation.html` | List all budget allocations |
| `ClientAccountsListView` | ListView | `admin-panel/users/` | `client_accounts.html` | User management |
| `AuditTrailListView` | ListView | `admin-panel/audit-trail/` | `audit_trail.html` | Transaction logs |
| `PRERequestListView` | ListView | `admin-panel/pre/` | `pre_list.html` | List all PRE submissions |
| `PREDetailView` | DetailView | `admin-panel/pre/<uuid:pk>/` | `pre_detail.html` | PRE detail with approval actions |
| `AdminPRListView` | ListView | `admin-panel/pr-requests/` | `pr_list.html` | List all PR submissions |
| `AdminPRDetailView` | DetailView | `admin-panel/pr-requests/<uuid:pr_id>/` | `pr_detail.html` | PR detail with approval actions |
| `DepartmentADRequestView` | ListView | `admin-panel/department/ad-requests/` | `departments_ad_request.html` | List all AD submissions |
| `HandleADRequestView` | View | `admin-panel/department/ad-requests/<uuid:pk>/handle/` | — | POST handler for AD actions |
| `AdminADDetailView` | DetailView | `admin-panel/department/ad-requests/<uuid:pk>/details/` | `view_ad_detail.html` | AD detail view |
| `AdminPREBudgetRealignmentListView` | ListView | `admin-panel/realignment/` | `pre_budget_realignment_list.html` | List realignment requests |
| `AdminPREBudgetRealignmentDetailView` | DetailView | `admin-panel/realignment/<int:pk>/` | `pre_budget_realignment_detail.html` | Realignment detail |
| `ArchiveCenterView` | TemplateView | `admin-panel/archive-center/` | `archive_center.html` | View/restore archived records |

### Function-Based Views

| View | URL | Purpose |
|------|-----|---------|
| `approved_budget_detail` | `admin-panel/approved_budget/<int:pk>/details/` | AJAX/detail for a single budget |
| `budget_allocation_detail` | `admin-panel/budget_allocation/<int:pk>/details/` | Allocation detail |
| `user_detail` | `admin-panel/users/<int:pk>/details/` | User detail |
| `toggle_user_status` | `admin-panel/users/<int:pk>/toggle-status/` | Activate/deactivate user |
| `bulk_user_action` | `admin-panel/users/bulk-action/` | Bulk user operations |
| `get_users_by_mfo` | `admin-panel/api/get-users-by-mfo/` | AJAX: filter users by MFO |
| `admin_handle_pre_action` | `admin-panel/pre/<uuid:pre_id>/action/` | PRE approve/reject |
| `admin_verify_and_approve_pre` | `admin-panel/pre/<uuid:pre_id>/verify/` | PRE final verification |
| `admin_upload_approved_document` | `admin-panel/pre/<uuid:pre_id>/upload-doc/` | Upload approved PRE doc |
| `handle_pr_action` | `admin-panel/pr-requests/<uuid:pr_id>/action/` | PR approve/reject |
| `admin_verify_and_approve_pr` | `admin-panel/pr-requests/<uuid:pr_id>/verify/` | PR final verification |
| `handle_admin_realignment_action` | `admin-panel/realignment/<int:pk>/action/` | Realignment approve/reject |
| `restore_archived_resource` | `admin-panel/archive-center/restore/<str:model_name>/<str:pk>/` | Restore archived item |
| `export_approved_budget_report_pdf` | `admin-panel/approved_budget/report/pdf/` | PDF report export |
| `export_budget_allocation_report_pdf` | `admin-panel/budget_allocation/report/pdf/` | PDF report export |
| `export_admin_pr_report_pdf` | `admin-panel/purchase_requests/report/pdf/` | PDF report export |
| `export_admin_ad_report_pdf` | `admin-panel/activity_designs/report/pdf/` | PDF report export |
| `export_admin_pre_report_pdf` | `admin-panel/pre/report/pdf/` | PDF report export |
| `export_admin_realignment_report_pdf` | `admin-panel/realignment/report/pdf/` | PDF report export |

---

## App: `end_user_panel`

All end-user views require `@login_required` or `LoginRequiredMixin`.

### Class-Based Views

| View | Type | URL | Template | Purpose |
|------|------|-----|----------|---------|
| `EndUserDashboardView` | TemplateView | `user/dashboard/` | `dashboard.html` | End user dashboard |
| `DepartmentPREPageView` | TemplateView | `user/department-pre/` | `department_pre_page.html` | List user's PREs with pagination |
| `UploadPREView` | View | `user/upload-pre/<int:allocation_id>/` | `upload_pre.html` | Upload PRE Excel file |
| `PreviewPREView` | TemplateView | `user/preview-pre/<uuid:pre_id>/` | `preview_pre.html` | Preview PRE before submit |
| `ViewPREDetailView` | DetailView | `user/view-pre/<uuid:pre_id>/` | `view_pre_detail.html` | PRE detail view |
| `ViewPRDetailView` | DetailView | `user/pr/view/<uuid:pr_id>/` | `view_pr_detail.html` | PR detail view |
| `ActivityDesignDetailView` | DetailView | `user/ad/view/<uuid:ad_id>/` | `view_ad_detail.html` | AD detail view |
| `PREBudgetRealignmentView` | View | `user/realignment/create/` | `pre_budget_realignment.html` | Create realignment |
| `PreviewRealignmentView` | DetailView | `user/realignment/<int:pk>/preview/` | `preview_realignment_documents.html` | Preview realignment |
| `UploadSignedRealignmentDocView` | View | `user/realignment/<int:pk>/upload-signed/` | — | Upload signed realignment doc |
| `PREBudgetRealignmentHistoryView` | ListView | `user/realignment/history/` | `realignment_history.html` | List realignment requests with pagination |
| `ArchiveHistoryView` | TemplateView | `user/archive/history/` | `archive_history.html` | View archived items |

### Function-Based Views

| View | URL | Purpose |
|------|-----|---------|
| `upload_approved_pre_documents` | `user/pre/<uuid:pre_id>/upload-signed-docs/` | Upload signed PRE documents |
| `budget_overview` | `user/budget/overview/` | Budget overview page |
| `pre_budget_details` | `user/budget/pre-details/` | PRE budget details |
| `quarterly_analysis` | `user/budget/quarterly/` | Quarterly analysis page |
| `transaction_history` | `user/budget/history/` | Transaction history page |
| `budget_reports` | `user/budget/reports/` | Reports page |
| `pr_ad_list` | `user/pr-ad-requests/` | List PRs and ADs with dual pagination |
| `purchase_request_upload` | `user/pr-ad-request/purchase_request_upload/` | Upload PR |
| `get_pre_line_items` | `user/get-pre-line-items/` | AJAX: get PRE line items for dropdown |
| `upload_signed_pr_docs` | `user/pr/<uuid:pr_id>/upload-signed-docs/` | Upload signed PR docs |
| `activity_design_upload` | `user/ad/upload/` | Upload AD |
| `upload_signed_ad_docs` | `user/ad/<uuid:ad_id>/upload-signed-docs/` | Upload signed AD docs |
| `get_realtime_line_item_amounts` | `user/api/get-realtime-amounts/` | AJAX: real-time line item budget |
| `archive_resource` | `user/archive/<str:resource_type>/<str:pk>/` | Archive a resource |
| `download_pre_template` | `user/download-template/` | Download Excel PRE template |
| `export_pre_budget_details_pdf` | `user/budget/pre-details/pdf/` | PDF report |
| `export_budget_summary_pdf` | `user/budget/reports/summary/pdf/` | PDF report |
| `export_quarterly_report_pdf` | `user/budget/reports/quarterly/pdf/` | PDF report |
| `export_category_report_pdf` | `user/budget/reports/category/pdf/` | PDF report |
| `export_transaction_report_pdf` | `user/budget/reports/transaction/pdf/` | PDF report |
