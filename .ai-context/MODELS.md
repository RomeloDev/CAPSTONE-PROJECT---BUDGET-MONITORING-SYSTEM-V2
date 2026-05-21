# MODELS

All models live in `apps/budgets/models.py` except the `User` model in `apps/user_accounts/models.py`.

---

## User Model (`apps/user_accounts/models.py`)

**`User`** — Custom user model extending `AbstractBaseUser` + `PermissionsMixin`

| Field | Type | Constraints |
|-------|------|------------|
| `id` | AutoField | PK |
| `username` | CharField(50) | `unique=True` |
| `fullname` | CharField(100) | Required |
| `email` | EmailField(255) | `unique=True` |
| `mfo` | CharField(255) | `null=True, blank=True` — Main department/office |
| `department` | CharField(255) | Required — specific sub-department |
| `position` | CharField(50) | `null=True, blank=True` |
| `is_admin` | BooleanField | `default=False` |
| `is_staff` | BooleanField | `default=False` — auto-set `True` when `is_admin=True` |
| `is_superuser` | BooleanField | `default=False` |
| `is_approving_officer` | BooleanField | `default=False` |
| `is_active` | BooleanField | `default=True` |
| `created_at` | DateTimeField | `default=timezone.now` |
| `updated_at` | DateTimeField | `auto_now=True` |
| `is_archived` | BooleanField | `default=False, db_index=True` |
| `archived_at` | DateTimeField | `null=True, blank=True` |
| `archived_by` | FK(self) | `SET_NULL, null=True, blank=True` |
| `archive_reason` | TextField | `blank=True` |
| `archive_type` | CharField(20) | choices: `FISCAL_YEAR`, `MANUAL` |

- `USERNAME_FIELD = "email"`
- `REQUIRED_FIELDS = ["username", "position", "fullname", "department"]`
- Managers: `objects = UserManager()`, `all_objects = models.Manager()`
- `save()` enforces: `if self.is_admin: self.is_staff = True`

---

## Budget Hierarchy

```
ApprovedBudget (fiscal year budget)
  └── BudgetAllocation (per department/end user)
        └── DepartmentPRE (expenditure plan)
              ├── PRELineItem (budget line items with Q1–Q4)
              │     ├── PurchaseRequestAllocation (PR funding link)
              │     └── ActivityDesignAllocation (AD funding link)
              └── PREReceipt (income items)
```

---

## Core Models

### `ApprovedBudget`
**Purpose:** The top-level fiscal year budget entry created by admin.

| Field | Type | Constraints |
|-------|------|------------|
| `title` | CharField(255) | |
| `fiscal_year` | CharField(10) | `unique_together=['fiscal_year']` |
| `amount` | DecimalField(15,6) | Total approved budget |
| `remaining_budget` | DecimalField(15,6) | Auto-set to `amount` on create |
| `description` | TextField | `blank=True` |
| `created_by` | FK(User) | `SET_NULL, null=True` |
| `created_at` | DateTimeField | `auto_now_add=True` |
| `updated_at` | DateTimeField | `auto_now=True` |
| `is_active` | BooleanField | `default=True` |
| Archive fields | Standard set | `is_archived`, `archived_at`, `archived_by`, `archive_reason`, `archive_type` |

- Managers: `objects = ArchiveManager()` (excludes archived), `all_objects = models.Manager()`
- `ARCHIVE_TYPE_CHOICES`: `FISCAL_YEAR`, `MANUAL`
- `save()`: sets `remaining_budget = amount` on first create

---

### `SupportingDocument`
**Purpose:** Supporting documents attached to an `ApprovedBudget`.

| Field | Type | Constraints |
|-------|------|------------|
| `approved_budget` | FK(ApprovedBudget) | `CASCADE`, related: `supporting_documents` |
| `document` | FileField | `upload_to=supporting_document_upload_path`, validators: pdf/docx/doc/xlsx/xls |
| `converted_pdf` | FileField | `upload_to='ab_converted_pdfs/%Y/%m/'`, `null=True, blank=True` |
| `file_name` | CharField(255) | |
| `file_format` | CharField(10) | `editable=False`, auto-detected |
| `file_size` | BigIntegerField | `editable=False`, auto-detected |
| `uploaded_by` | FK(User) | `SET_NULL, null=True` |
| `uploaded_at` | DateTimeField | `auto_now_add=True` |
| `description` | CharField(255) | `blank=True` |

**Has `converted_pdf`:** ✅ — for document preview system

---

### `BudgetAllocation`
**Purpose:** Distributes budget from `ApprovedBudget` to a specific department/end user.

| Field | Type | Constraints |
|-------|------|------------|
| `approved_budget` | FK(ApprovedBudget) | `CASCADE`, related: `allocations` |
| `department` | CharField(255) | |
| `end_user` | FK(User) | `CASCADE`, related: `budget_allocations` |
| `allocated_amount` | DecimalField(15,6) | |
| `remaining_balance` | DecimalField(15,6) | |
| `pre_amount_used` | DecimalField(15,6) | `default=0.00` |
| `pr_amount_used` | DecimalField(15,6) | `default=0.00` |
| `ad_amount_used` | DecimalField(15,6) | `default=0.00` |
| `allocated_at` | DateTimeField | `auto_now_add=True` |
| `is_active` | BooleanField | `default=True` |
| Archive fields | Standard set | |

- `unique_together = ['approved_budget', 'end_user']`
- `get_total_used()`: returns `pr_amount_used + ad_amount_used` (excludes PRE)
- `update_remaining_balance()`: `remaining_balance = allocated_amount - get_total_used()`
- `update_usage_from_prs()`: recalculates `pr_amount_used` from all Approved PRs

---

### `DepartmentPRE`
**Purpose:** Program of Receipts and Expenditures — the departmental budget plan.

| Field | Type | Constraints |
|-------|------|------------|
| `id` | UUIDField | PK, `default=uuid4` |
| `submitted_by` | FK(User) | `SET_NULL, null=True`, related: `submitted_pres` |
| `department` | CharField(255) | |
| `program` | CharField(255) | `null=True, blank=True` |
| `fund_source` | CharField(100) | `null=True, blank=True` |
| `fiscal_year` | CharField(10) | |
| `budget_allocation` | FK(BudgetAllocation) | `CASCADE`, related: `pres` |
| `uploaded_excel_file` | FileField | `upload_to='pre_uploads/%Y/%m/'`, validators: xlsx/xls |
| `uploaded_excel_pdf` | FileField | `upload_to='pre_converted_pdfs/%Y/%m/'`, `null=True, blank=True` |
| `status` | CharField(30) | See STATUS_CHOICES below |
| `is_valid` | BooleanField | `default=False` |
| `validation_errors` | JSONField | `default=dict` |
| `total_amount` | DecimalField(15,6) | `default=0.00` |
| `partially_approved_pdf` | FileField | `upload_to='pre_pdfs/%Y/%m/'` |
| `original_excel_pdf` | FileField | `upload_to='pre_pdfs/%Y/%m/'` |
| `final_approved_scan` | FileField | `upload_to='pre_scanned/%Y/%m/'` |
| `prepared_by_name` | CharField(255) | `blank=True` |
| `certified_by_name` | CharField(255) | `blank=True` |
| `approved_by_name` | CharField(255) | `blank=True` |
| `admin_notes` | TextField | `blank=True` |
| `rejection_reason` | TextField | `blank=True` |
| `awaiting_verification` | BooleanField | `default=False` |
| `end_user_uploaded_at` | DateTimeField | `null=True, blank=True` |
| `approved_documents` | FileField | `upload_to='pre_approved_docs/%Y/%m/'` |
| `admin_approved_at` | DateTimeField | `null=True, blank=True` |
| `admin_approved_by` | FK(User) | `SET_NULL`, related: `admin_approved_pres` |
| Timestamps | | `created_at`, `updated_at`, `submitted_at`, `partially_approved_at`, `final_approved_at` |
| Archive fields | Standard set | |

**STATUS_CHOICES:**
- `Draft` — Initial state
- `Pending` — Submitted for admin review
- `Partially Approved` — Admin has reviewed, awaiting physical signing
- `Awaiting Admin Verification` — End user uploaded signed docs
- `Approved` — Final approval
- `Rejected` — Rejected with reason

**Has `uploaded_excel_pdf`:** ✅ — converted PDF of Excel upload
**Has `rejection_reason`:** ✅

---

### `PurchaseRequest`
**Purpose:** Purchase request for procurement items.

| Field | Type | Constraints |
|-------|------|------------|
| `id` | UUIDField | PK, `default=uuid4` |
| `submitted_by` | FK(User) | `CASCADE`, related: `purchase_requests` |
| `department` | CharField(255) | |
| `pr_number` | CharField(50) | `unique=True` |
| `budget_allocation` | FK(BudgetAllocation) | `CASCADE`, related: `purchase_requests` |
| `source_pre` | FK(DepartmentPRE) | `SET_NULL, null=True, blank=True` |
| `source_line_item` | FK(PRELineItem) | `SET_NULL, null=True, blank=True` |
| `source_of_fund_display` | CharField(500) | `blank=True` |
| `purpose` | TextField | |
| `total_amount` | DecimalField(15,6) | `default=0.00` |
| `entity_name` | CharField(255) | `blank=True` |
| `fund_cluster` | CharField(100) | `blank=True` |
| `office_section` | CharField(255) | `blank=True` |
| `responsibility_center_code` | CharField(100) | `blank=True` |
| `uploaded_document` | FileField | `upload_to='pr_documents/%Y/%m/'`, validators: docx/doc/pdf |
| `uploaded_document_pdf` | FileField | `upload_to='pr_converted_pdfs/%Y/%m/'`, `null=True, blank=True` |
| `status` | CharField(50) | Same STATUS_CHOICES as PRE |
| `partially_approved_pdf` | FileField | `upload_to='pr/partially_approved_pdfs/'` |
| `approved_documents` | FileField | `upload_to='pr/approved_documents/'` |
| `final_approved_scan` | FileField | `upload_to='pr_scanned/%Y/%m/'` |
| `is_valid` | BooleanField | `default=False` |
| `validation_errors` | JSONField | `default=dict` |
| `admin_notes` | TextField | `blank=True` |
| `rejection_reason` | TextField | `blank=True` |
| `awaiting_verification` | BooleanField | `default=False` |
| `end_user_uploaded_at` | DateTimeField | `null=True, blank=True` |
| `admin_approved_by` | FK(User) | related: `pr_final_approvals` |
| `admin_approved_at` | DateTimeField | `null=True, blank=True` |
| `original_pr_pdf` | FileField | `upload_to='pr_original_pdfs/%Y/%m/'` |
| Timestamps | | `created_at`, `updated_at`, `submitted_at`, `partially_approved_at`, `final_approved_at` |
| Archive fields | Standard set | |

**Has `uploaded_document_pdf`:** ✅
**Has `rejection_reason`:** ✅
- `save()` triggers `budget_allocation.update_usage_from_prs()` after save

---

### `PurchaseRequestItem`
**Purpose:** Individual items in a form-based PR.

| Field | Type |
|-------|------|
| `purchase_request` | FK(PurchaseRequest), `CASCADE`, related: `items` |
| `stock_property_no` | CharField(100), `blank=True` |
| `unit` | CharField(50) |
| `item_description` | TextField |
| `quantity` | IntegerField |
| `unit_cost` | DecimalField(15,2) |
| `total_cost` | DecimalField(15,2), `editable=False` |

- `save()`: auto-calculates `total_cost = quantity * unit_cost`, updates parent PR `total_amount`

---

### `ActivityDesign`
**Purpose:** Activity Design for non-procurement requests.

| Field | Type | Constraints |
|-------|------|------------|
| `id` | UUIDField | PK, `default=uuid4` |
| `submitted_by` | FK(User) | `CASCADE`, related: `activity_designs` |
| `budget_allocation` | FK(BudgetAllocation) | `CASCADE`, related: `activity_designs` |
| `ad_number` | CharField(50) | `unique=True, blank=True` |
| `department` | CharField(255) | |
| `activity_title` | CharField(255) | `blank=True` |
| `activity_description` | TextField | `blank=True` |
| `purpose` | TextField | `blank=True` |
| `total_amount` | DecimalField(15,6) | |
| `uploaded_document` | FileField | `upload_to='ad_uploads/%Y/%m/'`, validators: docx/doc |
| `uploaded_document_pdf` | FileField | `upload_to='ad_converted_pdfs/%Y/%m/'`, `null=True, blank=True` |
| `status` | CharField(50) | Same STATUS_CHOICES as PRE |
| `original_ad_pdf` | FileField | `upload_to='ad/original_pdfs/'` |
| `partially_approved_pdf` | FileField | `upload_to='ad/partially_approved_pdfs/'` |
| `approved_documents` | FileField | `upload_to='ad/approved_documents/'` (DEPRECATED) |
| `final_approved_scan` | FileField | `upload_to='ad_scanned/%Y/%m/'` (DEPRECATED) |
| `awaiting_verification` | BooleanField | `default=False` |
| `end_user_uploaded_at` | DateTimeField | `null=True, blank=True` |
| `admin_approved_by` | FK(User) | related: `ad_final_approvals` |
| `admin_approved_at` | DateTimeField | |
| `is_valid` | BooleanField | `default=False` |
| `validation_errors` | JSONField | `default=dict` |
| `admin_notes` | TextField | `blank=True` |
| `rejection_reason` | TextField | `blank=True` |
| Timestamps | | `created_at`, `updated_at`, `submitted_at`, `partially_approved_at`, `final_approved_at` |
| Archive fields | Standard set | |

**Has `uploaded_document_pdf`:** ✅
**Has `rejection_reason`:** ✅

---

### `PRECategory`
**Purpose:** Budget categories (Personnel Services, MOOE, Capital Outlays)

| Field | Type |
|-------|------|
| `name` | CharField(100) |
| `category_type` | CharField(20), choices: `PERSONNEL`, `MOOE`, `CAPITAL` |
| `code` | CharField(20), `unique=True` |
| `is_active` | BooleanField |
| `sort_order` | IntegerField |

### `PRESubCategory`
**Purpose:** Sub-categories within main categories.

| Field | Type |
|-------|------|
| `category` | FK(PRECategory), `CASCADE`, related: `subcategories` |
| `name` | CharField(255) |
| `code` | CharField(50), `unique_together=['category', 'code']` |
| `is_active` | BooleanField |
| `sort_order` | IntegerField |

### `PRELineItem`
**Purpose:** Individual budget line items in a PRE with quarterly amounts.

| Field | Type |
|-------|------|
| `pre` | FK(DepartmentPRE), `CASCADE`, related: `line_items` |
| `category` | FK(PRECategory), `CASCADE` |
| `subcategory` | FK(PRESubCategory), `CASCADE`, `null=True, blank=True` |
| `item_name` | CharField(255) |
| `item_code` | CharField(50), `blank=True` |
| `description` | TextField, `blank=True` |
| `source_type` | CharField(20), choices: `excel`, `manual` |
| `q1_amount` | DecimalField(15,6), `default=0.00` |
| `q2_amount` | DecimalField(15,6), `default=0.00` |
| `q3_amount` | DecimalField(15,6), `default=0.00` |
| `q4_amount` | DecimalField(15,6), `default=0.00` |
| `is_procurable` | BooleanField |
| `procurement_method` | CharField(100), `blank=True` |
| `remarks` | TextField, `blank=True` |

Key methods: `get_total()`, `get_quarter_amount(quarter)`, `get_quarter_consumed(quarter)`, `get_quarter_reserved(quarter)`, `get_quarter_available(quarter)`, `get_quarter_breakdown(quarter)`

### `PREReceipt`
**Purpose:** Budget receipts/income for PRE.

| Field | Type |
|-------|------|
| `pre` | FK(DepartmentPRE), `CASCADE`, related: `receipts` |
| `receipt_type` | CharField(100) |
| `q1_amount` through `q4_amount` | DecimalField(15,6), `default=0.00` |

---

## Allocation Models

### `PurchaseRequestAllocation`
**Purpose:** Links a PR to specific PRE line items it draws funding from.

| Field | Type |
|-------|------|
| `purchase_request` | FK(PurchaseRequest), `CASCADE`, related: `pre_allocations` |
| `pre_line_item` | FK(PRELineItem), `PROTECT`, related: `pr_allocations` |
| `quarter` | CharField(2), choices: `Q1`, `Q2`, `Q3`, `Q4` |
| `allocated_amount` | DecimalField(15,6), `default=0.00` |
| `allocated_at` | DateTimeField, `auto_now_add=True` |
| `notes` | TextField, `blank=True` |

### `ActivityDesignAllocation`
**Purpose:** Same as above but for Activity Designs.

| Field | Type |
|-------|------|
| `activity_design` | FK(ActivityDesign), `CASCADE`, related: `pre_allocations` |
| `pre_line_item` | FK(PRELineItem), `PROTECT`, related: `ad_allocations` |
| `quarter` | CharField(2), choices: Q1–Q4 |
| `allocated_amount` | DecimalField(15,6) |
| `allocated_at` | DateTimeField |
| `notes` | TextField |

---

## Supporting/Approved Document Models

All follow the same pattern: `document` FileField + `converted_pdf` FileField + metadata.

| Model | Parent FK | Related Name | Has `converted_pdf` | Has `is_signed_copy` |
|-------|-----------|-------------|---------------------|---------------------|
| `SupportingDocument` | ApprovedBudget | `supporting_documents` | ✅ | ❌ |
| `DepartmentPRESupportingDocument` | DepartmentPRE | `supporting_documents` | ✅ | ❌ |
| `PurchaseRequestSupportingDocument` | PurchaseRequest | `supporting_documents` | ✅ | ✅ |
| `ActivityDesignSupportingDocument` | ActivityDesign | `supporting_documents` | ✅ | ✅ |
| `BudgetRealignmentSupportingDocument` | PREBudgetRealignment | `supporting_documents` | ✅ | ✅ |
| `DepartmentPREApprovedDocument` | DepartmentPRE | `signed_approved_documents` | ❌ | ❌ |
| `PurchaseRequestApprovedDocument` | PurchaseRequest | `signed_approved_documents` | ✅ | ❌ |
| `ActivityDesignApprovedDocument` | ActivityDesign | `signed_approved_documents` | ✅ | ❌ |

**Why `converted_pdf` exists:** The 3-tier preview system needs to display non-PDF files (DOCX, XLSX) in an iframe. The `converted_pdf` field caches the LibreOffice-generated PDF so conversion only happens once per document.

---

## Draft Models

| Model | Purpose | User FK Type |
|-------|---------|-------------|
| `PREDraft` | Temporary PRE Excel upload before submission | FK(User) |
| `PREDraftSupportingDocument` | Docs attached to PRE draft | FK(PREDraft) |
| `PRDraft` | Temporary PR document before submission | OneToOne(User) |
| `PRDraftSupportingDocument` | Docs attached to PR draft | FK(PRDraft) |
| `ADDraft` | Temporary AD document before submission | OneToOne(User) |
| `ADDraftSupportingDocument` | Docs attached to AD draft | FK(ADDraft) |

---

## Budget Realignment

### `PREBudgetRealignment`
**Purpose:** Transfer budget between PRE line items across quarters.

| Field | Type | Notes |
|-------|------|-------|
| `requested_by` | FK(User) | `SET_NULL` |
| `approved_by` | FK(User) | `SET_NULL, blank=True` |
| `status` | CharField(50) | Same STATUS_CHOICES as PRE |
| `reason` | TextField | `blank=True` |
| `source_pre` | FK(DepartmentPRE) | related: `source_budget_realignments` |
| `source_item_key` | CharField(255) | Stores PRELineItem ID |
| `target_pre` | FK(DepartmentPRE) | related: `target_budget_realignments` |
| `target_item_key` | CharField(255) | Stores PRELineItem ID |
| `q1_amount` through `q4_amount` | DecimalField(12,2) | Per-quarter transfer amounts |
| `amount` | DecimalField(12,2) | Auto-calculated total |
| `source_item_display` | CharField(500) | Human-readable source |
| `target_item_display` | CharField(500) | Human-readable target |
| `rejection_reason` | TextField | `blank=True` |
| Document fields | FileFields | `partially_approved_pdf`, `approved_documents`, `final_approved_scan`, `end_user_uploaded_document` |
| Approval tracking | Various | `approved_by_approving_officer`, `approved_by_admin`, timestamps |
| Archive fields | Standard set | |

**Has `rejection_reason`:** ✅

---

## Audit and Reporting Models

### `BudgetTransaction`
**Purpose:** Tracks financial movements (audit trail).

| Field | Type |
|-------|------|
| `allocation` | FK(BudgetAllocation), related: `transactions` |
| `transaction_type` | CharField(50) |
| `amount` | DecimalField(15,2) |
| `previous_balance` | DecimalField(15,2) |
| `new_balance` | DecimalField(15,2) |
| `remarks` | TextField, `blank=True` |
| `created_by` | FK(User), `SET_NULL` |
| `created_at` | DateTimeField |

### `BudgetTransactionLog`
**Purpose:** Detailed transaction log with typed entries.

- `TRANSACTION_TYPES`: `PRE_APPROVED`, `PR_APPROVED`, `AD_APPROVED`, `PRE_REJECTED`, `PR_REJECTED`, `AD_REJECTED`, `ALLOCATION_CREATED`, `ALLOCATION_MODIFIED`, `ALLOCATION_DELETED`, `REALIGNMENT_APPROVED`

### `RequestApproval`
**Purpose:** Generic approval tracking across PRE/PR/AD.

### `SystemNotification`
**Purpose:** In-app notifications for status changes.

### `BudgetSavings` / `PRELineItemSavings`
**Purpose:** Snapshot of unused budget at end of fiscal period for analytics.

---

## Models with `rejection_reason` field

1. `DepartmentPRE` — `rejection_reason = TextField(blank=True)`
2. `PurchaseRequest` — `rejection_reason = TextField(blank=True)`
3. `ActivityDesign` — `rejection_reason = TextField(blank=True)`
4. `PREBudgetRealignment` — `rejection_reason = TextField(blank=True)`

---

## Models with `converted_pdf` field (9 total)

1. `SupportingDocument` — `converted_pdf`
2. `DepartmentPRE` — `uploaded_excel_pdf`
3. `PurchaseRequest` — `uploaded_document_pdf`
4. `ActivityDesign` — `uploaded_document_pdf`
5. `DepartmentPRESupportingDocument` — `converted_pdf`
6. `PurchaseRequestSupportingDocument` — `converted_pdf`
7. `ActivityDesignSupportingDocument` — `converted_pdf`
8. `BudgetRealignmentSupportingDocument` — `converted_pdf`
9. `PurchaseRequestApprovedDocument` — `converted_pdf`
10. `ActivityDesignApprovedDocument` — `converted_pdf`

*(10 total — each has a corresponding `post_delete` signal handler for cleanup)*
