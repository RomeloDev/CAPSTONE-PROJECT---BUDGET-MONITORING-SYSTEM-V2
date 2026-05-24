# TASK TRACKER

**Deployment Deadline: May 25, 2026**

---

## ✅ Completed Features

### Core Infrastructure

- [x] Local file storage migration (Cloudinary fully removed)
- [x] `FileSystemStorage` configured as default storage backend
- [x] Media files served via local filesystem (`media/` directory)
- [x] WhiteNoise configured for static file serving

### 3-Tier Document Preview System

- [x] `document-preview.js` — shared preview system with `openPreview()` function
- [x] Tier 0: Pre-check for existing converted PDF
- [x] Tier 1: Google Docs Viewer with 8-second timeout
- [x] Tier 2: LibreOffice AJAX conversion via `/budgets/api/convert-to-pdf/`
- [x] Tier 3: Download fallback with styled error message
- [x] Deployed to all 8 detail templates:
  - [x] `admin_panel/pr_detail.html`
  - [x] `admin_panel/pre_detail.html`
  - [x] `admin_panel/view_ad_detail.html`
  - [x] `admin_panel/pre_budget_realignment_detail.html`
  - [x] `admin_panel/approved_budget.html`
  - [x] `end_user_panel/view_pr_detail.html`
  - [x] `end_user_panel/view_pre_detail.html`
  - [x] `end_user_panel/view_ad_detail.html`
  - [x] `end_user_panel/preview_realignment_documents.html`

### LibreOffice AJAX Conversion Endpoint

- [x] `convert_document_to_pdf` view with whitelist validation
- [x] `DOCUMENT_TYPE_MAP` covering all 10 document types
- [x] `convert_to_pdf_with_libreoffice()` utility function
- [x] `attach_converted_pdf()` utility function
- [x] `CREATE_NO_WINDOW` flag for Windows
- [x] `post_delete` signal handlers for all 10 models with converted PDF fields

### Rejection Comment Modals

- [x] PRE rejection modal (`admin_panel/pre_detail.html`)
- [x] PR rejection modal — both stages (`admin_panel/pr_detail.html`)
- [x] AD rejection modal — both Pending and Awaiting Verification stages (`admin_panel/view_ad_detail.html`)
  - `adRejectModal` for Pending stage
  - `adVerifyRejectModal` for Awaiting Verification stage
  - Final Approve button: `confirm()` removed, now plain submit
- [x] Budget Realignment rejection modal (`admin_panel/pre_budget_realignment_detail.html`)

### Gmail Email Notifications

- [x] `apps/budgets/notifications.py` — fire-and-forget notification service
- [x] `notify_admins_new_request()` — notifies admin on new submissions
- [x] `notify_user_status_change()` — notifies end user on status changes
- [x] Gmail SMTP configuration in `settings.py`

### End User Panel Pagination

- [x] `purchase_request_list.html` — dual pagination (`pr_page` + `ad_page`)
- [x] `department_pre_page.html` — single pagination (`page`)
- [x] `realignment_history.html` — single pagination (was already implemented)

### Admin Panel Pagination

- [x] `approved_budget.html` / `ApprovedBudgetListView` — lists all approved budgets
- [x] `budget_allocation.html` / `BudgetAllocationListView` — lists all allocations
- [x] `pre_list.html` / `PRERequestListView` — lists all PRE submissions
- [x] `pr_list.html` / `AdminPRListView` — lists all PR submissions
- [x] `departments_ad_request.html` / `DepartmentADRequestView` — lists all AD submissions
- [x] `pre_budget_realignment_list.html` / `AdminPREBudgetRealignmentListView` — lists realignment requests
- [x] `audit_trail.html` / `AuditTrailListView` — lists transaction logs

### Planning

- [x] Admin panel pagination audit
  - Implementation plan at .ai-plans/admin_pagination_plan.md
  - Implementation complete: approved_budget, budget_allocation, pr_list, departments_ad_request, pre_list, pre_budget_realignment_list, audit_trail

### Deployment Guide

- [x] `deployment/nginx.conf` — Nginx reverse proxy configuration
- [x] `deployment/README.md` — Complete 14-section deployment guide

---

## ⏳ Pending Features (Before May 25 Deployment)

### Admin Panel Pagination

- [ ] `client_accounts.html` / `ClientAccountsListView` — lists all users
- [ ] `archive_center.html` / `ArchiveCenterView` — lists archived records

### UI/UX Polish

- [x] Default fiscal year filters to current year instead of "All Years" (approved_budget, budget_allocation)
- [ ] Consistent styling across all templates (admin and end user)
- [ ] Loading states on all form submissions
- [ ] Empty state messages when no data exists (e.g., "No purchase requests found")
- [ ] Consistent button styles and hover effects
- [ ] Mobile responsiveness audit
- [ ] Form validation feedback (client-side)

### Testing

- [ ] Manual end-to-end testing of all 4 workflows (PRE, PR, AD, Realignment)
- [ ] Document preview testing across file types (PDF, DOCX, XLSX, JPG, PNG)
- [ ] Rejection modal testing — verify reason is saved and displayed
- [ ] Pagination testing — verify GET params preserved in dual-paginator
- [ ] Budget calculation testing — verify deductions and returns
- [ ] Email notification testing — verify Gmail delivery
- [ ] File upload size limit testing (50 MB boundary)
- [ ] Archive and restore testing
- [ ] Cross-browser testing (Chrome, Firefox, Edge)

### Bug Fixes

- [x] Fixed missing `href` on the download button in the document preview modal header by dynamically updating it in `document-preview.js`.

### Final Deployment Tasks

- [ ] PostgreSQL database setup on production server
- [ ] LibreOffice installation on production server
- [ ] Nginx configuration with actual server IP
- [ ] Gunicorn systemd service setup
- [ ] SSL certificate (if campus network requires HTTPS)
- [ ] `.env` file with production values
- [ ] `python manage.py migrate --noinput`
- [ ] `python manage.py collectstatic --noinput`
- [ ] Create initial admin user
- [ ] Verify all 13 checks in deployment README verification checklist
- [ ] Backup strategy in place (PostgreSQL + media/)
