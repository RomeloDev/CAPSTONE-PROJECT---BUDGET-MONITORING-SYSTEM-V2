# KNOWN ISSUES

Documented issues, gotchas, and edge cases that any AI agent working on this codebase must be aware of.

---

## 🚨 CRITICAL PENDING FIX: AD Source of Fund Duplicate Bug (Resolved)

**Issue:** A critical vulnerability existed in the Activity Design (AD) creation form where already-selected Source of Fund line items remained visible/selectable in the dropdown, allowing duplicate line item usage. This bypassed budget limits and corrupted the deduction logic.
**Status:** **RESOLVED** (Pending Execution). Implementation plan written and approved.
**Finding:** During implementation planning, it was verified that the AD draft allocation system (session-based) does **not** apply temporary deductions to a line item's available balance across concurrent sessions, nor does it use `select_for_update()` during final submission. This means concurrent submissions from two users could theoretically over-allocate. For a campus LAN system with few concurrent users, this is an acceptable risk for now.

---

## 1. X_FRAME_OPTIONS Must Be SAMEORIGIN

**Setting:** `X_FRAME_OPTIONS = 'SAMEORIGIN'` in `config/settings.py` (line 177)

**Why:** The document preview system uses `<iframe>` elements to display PDFs and converted documents. If `X_FRAME_OPTIONS` is set to `DENY`, all iframe-based previews will break with a blank frame. This must remain `SAMEORIGIN`.

**Nginx echo:** The nginx.conf also sets `add_header X-Frame-Options "SAMEORIGIN" always;` — both must be consistent.

---

## 2. Google Docs Viewer Cannot Reach Private LAN IPs

**Symptom:** Tier 1 (Google Docs Viewer) always fails on the campus LAN deployment.

**Why:** The server is on a private IP (e.g., `192.168.x.x`) that Google's servers cannot reach over the internet. The Google Docs Viewer iframe loads but shows an error page.

**By design:** This is expected behavior. The 8-second timeout in `document-preview.js` triggers Tier 2 (LibreOffice AJAX conversion) automatically. On campus LAN, Tier 1 is effectively a no-op — Tier 2 is always the real preview mechanism.

**Do not attempt to "fix" Tier 1 for LAN** — the timeout mechanism works correctly.

---

## 3. iframe.onload Fires Even When Google Docs Fails

**Symptom:** `iframe.onload` fires even when Google Docs shows an error page.

**Why:** The iframe considers the page "loaded" regardless of content. Google Docs returns an HTML page (even an error page), which triggers `onload`.

**Solution in code:** `onload` only removes the spinner and reveals the iframe. It does **not** clear the Tier 2 timeout. The 8-second timeout is the **sole** Tier 2 trigger — `onload` is explicitly not trusted.

```javascript
// onload only removes the spinner and reveals the iframe.
// It does NOT clear the timeout — Tier 2 still fires regardless.
iframe.onload = () => {
    const spinner = document.getElementById('previewSpinner');
    if (spinner) spinner.remove();
    iframe.style.display = '';
};
```

---

## 4. LibreOffice CREATE_NO_WINDOW Flag on Windows

**Issue:** Without `CREATE_NO_WINDOW`, LibreOffice opens a visible console window on each conversion, causing a visual flash.

**Solution in code:**
```python
creationflags=(subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
```

This flag is only applied on Windows (`os.name == 'nt'`). On Linux, it's `0` (no flag).

---

## 5. Draft Supporting Documents Excluded from Conversion

**By design:** Draft-stage documents (`PREDraft`, `PRDraft`, `ADDraft` and their supporting documents) do not have `converted_pdf` fields and are not in the `DOCUMENT_TYPE_MAP`. Preview is not available for drafts — only for submitted documents.

**Rationale:** Drafts are temporary and may be deleted/resubmitted. Converting them would waste server resources.

---

## 6. Dual Paginator GET Params Must Both Be Preserved

**Applies to:** `purchase_request_list.html` with `pr_page` and `ad_page` params.

**Issue:** If a pagination link only includes its own param (e.g., `?pr_page=2`), the other paginator resets to page 1.

**Solution:** Every pagination link must include both params:
```html
<a href="?pr_page={{ page_obj_pr.next_page_number }}&ad_page={{ page_obj_ad.number }}">
```

---

## 7. Template-Level Draft Filter Corrupts Pagination Counts

**Issue:** If you filter out `Draft` status items in the template (using `{% if obj.status != 'Draft' %}`), the pagination count will be wrong because the paginator counted all items including drafts.

**Solution:** Always exclude drafts in the queryset/view, never in the template:
```python
queryset = PurchaseRequest.objects.filter(submitted_by=user).exclude(status='Draft')
```

---

## 8. Document Type Whitelist Must Be Updated for New Models

**Where:** `DOCUMENT_TYPE_MAP` in `apps/budgets/views.py`

**Issue:** When adding a new model with a `converted_pdf` field, the `DOCUMENT_TYPE_MAP` must be updated with a new entry, otherwise the preview system won't know how to convert documents for that model.

**Checklist for adding a new previewable document model:**
1. Add `converted_pdf` FileField to the model
2. Add entry to `DOCUMENT_TYPE_MAP` in `budgets/views.py`
3. Add `post_delete` signal handler in `budgets/signals.py`
4. Update template to call `openPreview()` with correct `docType` parameter

---

## 9. post_delete Signal Must Be Added for New Converted PDF Fields

**Where:** `apps/budgets/signals.py`

Every model with a `converted_pdf` (or equivalent) field must have a `post_delete` signal handler to clean up the file from disk when the record is deleted.

**Pattern:**
```python
@receiver(post_delete, sender=NewModel)
def cleanup_new_model_pdf(sender, instance, **kwargs):
    if instance.converted_pdf:
        instance.converted_pdf.delete(save=False)
```

---

## 10. SupportingDocument.converted_pdf Was Added Late

**History:** The `SupportingDocument` model (for `ApprovedBudget` supporting documents) originally did not have a `converted_pdf` field. It was added during the local storage migration phase.

**Action required:** Verify that the migration for this field has been applied in production:
```bash
python manage.py showmigrations budgets
```

Look for the migration that adds `converted_pdf` to `SupportingDocument`.

---

## 11. Duplicate Function Definitions in models.py

**Issue:** There are standalone function definitions at module level (lines 1733-1791) that duplicate methods already defined on the `PurchaseRequest` and `ActivityDesign` classes:
- `get_allocated_line_items()`
- `get_total_allocated_from_pre()`
- `get_allocation_summary()`

These standalone functions are dead code — the class methods on the models are what's actually used. They appear to be leftover from a refactoring where methods were moved into the classes but the originals weren't deleted.

**Risk:** Low — they're not imported or called anywhere. Can be safely deleted.

---

## 12. DepartmentPRE Has Duplicate Timestamp Fields

**Issue:** `DepartmentPRE` defines `submitted_at`, `partially_approved_at`, and `final_approved_at` twice — once at lines 481-483 and again at lines 490-492. Django uses the last definition, so lines 481-483 are effectively dead.

**Risk:** Low — Django handles this gracefully (last definition wins). But it's confusing for maintainability.

---

## 13. Render.com Legacy Code in settings.py

**Issue:** `settings.py` lines 24-29 contain code that dynamically adds `RENDER_EXTERNAL_HOSTNAME` to `ALLOWED_HOSTS`. This was from a previous cloud deployment on Render.com but is no longer used for the campus LAN deployment.

**Risk:** None — the env var is never set in the campus deployment, so the code is a no-op. Can be removed for clarity.

---

## 14. BudgetAllocation pre_save Signal Race Condition Potential

**Issue:** The `cache_old_allocation_values` pre_save signal caches old values as instance attributes (`_old_allocated_amount`, `_old_approved_budget_id`) before save. If two requests modify the same allocation concurrently, the cached values could be stale.

**Mitigation:** The `sync_parent_budget_on_allocation_save` post_save handler uses `transaction.atomic()` and `F()` expressions for the actual database update, which provides atomic updates. The race condition window is narrow and low-risk for this use case.

---

## 15. PREBudgetRealignment Uses Integer PK (Not UUID)

**Unlike** `DepartmentPRE`, `PurchaseRequest`, and `ActivityDesign` which use `UUIDField` as PK, `PREBudgetRealignment` uses Django's default `AutoField` (integer PK). URL patterns use `<int:pk>` for realignment views vs `<uuid:pk>` for others.

**Risk:** None — just be aware when constructing URLs or form actions.

---

## 16. ActivityDesign Has Deprecated Fields

The following fields on `ActivityDesign` are marked as deprecated in their `help_text`:
- `approved_documents` — replaced by `signed_approved_documents` (via `ActivityDesignApprovedDocument`)
- `final_approved_scan` — deprecated

These fields still exist in the database and may contain data from earlier submissions. Don't add new code that writes to them.

---

## 17. Fiscal Year Default Filter

**Issue:** By default, the `approved_budget` and `budget_allocation` list views now automatically pre-filter by the current fiscal year if no GET parameter is specified. This is to avoid showing all years by default, which can cause performance/visual clutter.

**Implementation:**
- `get_queryset` in both `ApprovedBudgetListView` and `BudgetAllocationListView` defaults `summary_year` to `str(date.today().year)` if `fiscal_year` and `summary_year` are absent from the request.
- Both views pass `current_year` to the template context.
- In both templates, the card filter dropdown defaults to the current year when loaded fresh without filters.
- The templates were unified to both use `name="summary_year"` for the card filter and `name="fiscal_year"` for the filter modal, preventing the bug where the form filter would cancel out the card filter state.

---

## 18. Missing Modal Download Link

**Issue:** PR detail admin template had missing download button href. Scenario B applied: The download button inside the preview modal header was hardcoded with `href="#"` and was not connected to the preview system JS.

**Fix:** Fixed by updating `document-preview.js` to dynamically set the `href` of `downloadLink` to the `originalUrl` when `openPreview()` is called, ensuring it automatically provides the correct download link for all document types (main document, supporting documents, signed copies) sharing the same modal.
