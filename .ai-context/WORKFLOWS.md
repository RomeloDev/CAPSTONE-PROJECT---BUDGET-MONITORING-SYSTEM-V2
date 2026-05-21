# WORKFLOWS

---

## 1. PRE Approval Workflow

The PRE (Program of Receipts and Expenditures) is the departmental budget plan that must be approved before a department can submit PRs or ADs.

### Step-by-Step Flow

1. **End User creates PRE Draft** (`PREDraft` model)
   - User selects a `BudgetAllocation` and uploads an Excel file (`.xlsx/.xls`)
   - Optionally attaches supporting documents (`PREDraftSupportingDocument`)
   - The system parses the Excel file and creates `PRELineItem` entries

2. **End User submits PRE** → status changes `Draft → Pending`
   - `DepartmentPRE` record created from the draft
   - `submitted_at` timestamp set
   - Draft data is migrated to the permanent model
   - Email notification sent to admin (via `notifications.py`)

3. **Admin reviews PRE** (`admin_handle_pre_action` view)
   - Admin can view the uploaded Excel, line items, and supporting documents
   - **Partial Approve** → status: `Partially Approved`
     - `partially_approved_at` set
     - PDF generated from database line items (`partially_approved_pdf`)
     - Original Excel PDF preserved (`original_excel_pdf`)
   - **Reject** → status: `Rejected`
     - `rejection_reason` field populated from modal textarea
     - End user sees rejection banner with reason text

4. **End User prints and gets physical signatures**
   - Downloads the `partially_approved_pdf`
   - Prints it, gets signatures from Approving Officer
   - Scans or photographs the signed document

5. **End User uploads signed documents** (`upload_approved_pre_documents` view)
   - Creates `DepartmentPREApprovedDocument` records
   - Status: `Partially Approved` → `Awaiting Admin Verification`
   - `awaiting_verification = True`
   - `end_user_uploaded_at` set

6. **Admin verifies and gives final approval** (`admin_verify_and_approve_pre` view)
   - Admin uploads final approved document (`approved_documents` field)
   - Status: `Awaiting Admin Verification` → `Approved`
   - `approve_with_documents(admin_user)` called:
     - `final_approved_at` set
     - `admin_approved_by` and `admin_approved_at` set
     - `budget_allocation.pre_amount_used` updated with correct total from line items
     - `budget_allocation.update_remaining_balance()` called
   - Approved PRE line items become available as funding sources for PRs and ADs

---

## 2. Purchase Request Workflow

### Step-by-Step Flow

1. **End User creates PR Draft** (`PRDraft` model)
   - Uploads a PR document (`.docx/.doc/.pdf`)
   - Selects a PRE line item as funding source
   - Selects quarter and enters amount
   - Attaches supporting documents

2. **End User submits PR** → status: `Draft → Pending`
   - `PurchaseRequest` record created with `PurchaseRequestAllocation` linking to PRE line items
   - `submitted_at` set
   - `pr_number` auto-generated
   - **Temporary budget reservation:** The allocation is tracked in `PurchaseRequestAllocation` — `get_quarter_reserved()` counts Pending status PRs, preventing double-booking
   - Email notification sent to admin

3. **Admin reviews PR** (`handle_pr_action` view)
   - **Partial Approve** → status: `Partially Approved`
     - `partially_approved_at` set
     - PDF generated (`partially_approved_pdf`)
   - **Reject** → status: `Rejected`
     - `rejection_reason` populated
     - Budget reservation released (PR no longer counts in `get_quarter_reserved()`)

4. **End User prints, gets signatures, uploads signed copy** (`upload_signed_pr_docs`)
   - Creates `PurchaseRequestApprovedDocument` records
   - Status: `Partially Approved` → `Awaiting Admin Verification`

5. **Admin verifies and gives final approval** (`admin_verify_and_approve_pr`)
   - Status: `Awaiting Admin Verification` → `Approved`
   - Budget officially consumed:
     - `budget_allocation.update_usage_from_prs()` recalculates `pr_amount_used` from all Approved PRs
     - `budget_allocation.update_remaining_balance()` updates `remaining_balance`

---

## 3. Activity Design Workflow

Same pattern as Purchase Request with these differences:

- Uses `ActivityDesign` model and `ActivityDesignAllocation`
- Document upload is `.docx/.doc` only (no PDF upload)
- `ad_number` auto-generated
- Uses `ad_amount_used` on `BudgetAllocation`
- **Two-stage reject:** Both the `Pending` stage and `Awaiting Admin Verification` stage have reject buttons with modal-based rejection forms (`adRejectModal` and `adVerifyRejectModal` in `view_ad_detail.html`)

### Handle View: `HandleADRequestView`
- Handles POST actions: `approve`, `reject`, `approve_final`
- For `approve`: generates `partially_approved_pdf`, original converted to `original_ad_pdf`
- For `reject`: captures `rejection_reason` from POST data
- For `approve_final`: updates `ad_amount_used` on budget allocation

---

## 4. Budget Realignment Workflow

### Step-by-Step Flow

1. **End User creates realignment request** (`PREBudgetRealignmentView`)
   - Selects source PRE line item and target PRE line item
   - Enters per-quarter transfer amounts (`q1_amount` through `q4_amount`)
   - System validates source has sufficient funds per quarter
   - Attaches supporting documents

2. **Submit** → status: `Pending`
   - `PREBudgetRealignment` record created
   - Amount auto-calculated: `amount = q1 + q2 + q3 + q4`

3. **Admin reviews** (`handle_admin_realignment_action`)
   - **Partial Approve** → status: `Partially Approved`
     - PDF generated
   - **Reject** → status: `Rejected`
     - `rejection_reason` populated

4. **End User uploads signed document** → status: `Awaiting Admin Verification`
   - `end_user_uploaded_document` field populated

5. **Admin final approval** → status: `Approved`
   - `_execute_budget_realignment()` called within `transaction.atomic()`:
     - For each quarter with non-zero amount:
       - Source line item's `qN_amount` decreased
       - Target line item's `qN_amount` increased

---

## 5. Budget Deduction Logic

### When temporary reservations happen
- **On PR/AD submission** (status = `Pending`): The amount is tracked via `PurchaseRequestAllocation` / `ActivityDesignAllocation` records. The `get_quarter_reserved()` method on `PRELineItem` counts these as "reserved" budget.
- **On partial approval** (status = `Partially Approved`): Still counted as reserved.

### When budget is officially consumed
- **On final approval** (status = `Approved`):
  - `BudgetAllocation.update_usage_from_prs()` recalculates `pr_amount_used` from all Approved PRs
  - `BudgetAllocation.update_remaining_balance()` recalculates `remaining_balance = allocated_amount - (pr_amount_used + ad_amount_used)`
  - At the line item level, `get_quarter_consumed()` only counts `Approved` status

### When budget is returned
- **On rejection**: PR/AD status becomes `Rejected`, which is excluded from both `get_quarter_reserved()` and `get_quarter_consumed()` calculations. The `update_usage_from_prs()` method automatically recalculates.

### How double-booking is prevented
- `get_quarter_available(quarter)` = `quarter_amount - consumed - reserved`
- Both `Pending` and `Partially Approved` statuses count as "reserved"
- The submission form checks available budget before allowing submission
- Quarterly validation (`validate_quarterly_limits()`) ensures per-quarter limits are respected

---

## 6. Rejection Comment Capture

### Standard POST field name: `rejection_reason`

All rejection modals use the same pattern:
- A hidden `<div>` containing a `<form>` with:
  - `<input type="hidden" name="action" value="reject">`
  - `<textarea name="rejection_reason" minlength="10" required>`
  - `{% csrf_token %}`
- The modal is opened via `onclick="document.getElementById('...Modal').classList.remove('hidden')"`

### Models that store it
1. `DepartmentPRE.rejection_reason`
2. `PurchaseRequest.rejection_reason`
3. `ActivityDesign.rejection_reason`
4. `PREBudgetRealignment.rejection_reason`

### Views that read it
- `admin_handle_pre_action`: `request.POST.get('rejection_reason', '')`
- `handle_pr_action`: `request.POST.get('rejection_reason', '')`
- `HandleADRequestView.post()`: `request.POST.get('rejection_reason', '')`
- `handle_admin_realignment_action`: `request.POST.get('rejection_reason', '')`

### Display
- Admin sees a red rejection reason card when `status == 'Rejected'` and `rejection_reason` is non-empty
- End user sees a rejection banner with the reason text in their detail view
