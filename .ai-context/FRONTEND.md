# FRONTEND

---

## Template Directory Structure

### Admin Panel (`apps/admin_panel/templates/admin_panel/`)

| Template | Purpose |
|----------|---------|
| `dashboard.html` | Admin dashboard with summary stats, charts, quick actions |
| `approved_budget.html` | List approved budgets, upload documents, view details modal |
| `budget_allocation.html` | List and manage budget allocations per department |
| `client_accounts.html` | User management — list, create, toggle status, bulk actions |
| `pre_list.html` | List all PRE submissions with status filters |
| `pre_detail.html` | PRE detail with line items, documents, approve/reject actions |
| `pr_list.html` | List all PR submissions |
| `pr_detail.html` | PR detail with documents, approve/reject modals, verify flow |
| `view_ad_detail.html` | AD detail with documents, approve/reject modals, verify flow |
| `departments_ad_request.html` | List all AD submissions |
| `pre_budget_realignment_list.html` | List budget realignment requests |
| `pre_budget_realignment_detail.html` | Realignment detail with approve/reject |
| `audit_trail.html` | Budget transaction audit log |
| `archive_center.html` | View and restore archived records |
| `partials/` | Reusable template fragments |

### End User Panel (`apps/end_user_panel/templates/end_user_panel/`)

| Template | Purpose |
|----------|---------|
| `dashboard.html` | End user dashboard with budget summary |
| `department_pre_page.html` | List user's PREs with pagination (page param) |
| `upload_pre.html` | Upload PRE Excel file with drag-and-drop |
| `preview_pre.html` | Preview parsed PRE before submission |
| `view_pre_detail.html` | PRE detail with full document preview |
| `purchase_request_list.html` | List PRs and ADs with dual pagination (pr_page, ad_page) |
| `purchase_request_upload_form.html` | Upload/create PR with PRE line item selection |
| `view_pr_detail.html` | PR detail with documents, signed doc upload |
| `activity_design_upload.html` | Upload AD document |
| `view_ad_detail.html` | AD detail with documents, signed doc upload |
| `pre_budget_realignment.html` | Create budget realignment request |
| `preview_realignment_documents.html` | Preview realignment before submission |
| `realignment_history.html` | Realignment history with pagination |
| `budget_overview.html` | Budget overview charts and stats |
| `pre_budget_details.html` | Detailed PRE budget breakdown |
| `quarterly_analysis.html` | Quarterly budget analysis |
| `transaction_history.html` | Budget transaction history |
| `budget_reports.html` | Budget reports with export options |
| `archive_history.html` | View archived items |
| `partials/` | Reusable template fragments |

---

## Shared JavaScript Files

### `static/js/document-preview.js`
The shared 3-tier document preview system used across all 8 detail templates.

**Function signatures:**

```javascript
// Main entry point — called by all template preview buttons
function openPreview(originalUrl, convertedPdfUrl, docId, docType, title)
// Parameters:
//   originalUrl     — URL of the original file (relative or absolute)
//   convertedPdfUrl — URL of already-converted PDF, or empty string ''
//   docId           — model instance PK (UUID string or integer)
//   docType         — one of the DOCUMENT_TYPE_MAP keys (e.g., 'pr_main', 'pre_supporting_doc')
//   title           — optional title shown in modal header (5th param, optional)

// Close and reset
function closePreviewModal()

// Internal — AJAX LibreOffice conversion
function _triggerTier2(originalUrl, docId, docType)

// Internal — get CSRF token
function _getCsrfToken()
```

**PreviewState object:**
```javascript
const PreviewState = {
    _timeout: null,        // Tier 2 timer handle
    _abortController: null, // Fetch abort controller
    showLoading(message),  // Show spinner with message
    showIframe(url),       // Show document in iframe
    showImage(url),        // Show image preview
    showError(originalUrl), // Show download fallback
    reset(),               // Clear timeout and abort controller
}
```

**3-Tier Preview Logic:**

1. **Tier 0 (Pre-check):** If `convertedPdfUrl` is non-empty → show PDF iframe immediately
2. **Native PDF:** If file extension is `.pdf` → show iframe directly
3. **Native Image:** If extension is `jpg/jpeg/png/gif/webp` → show `<img>` tag
4. **Tier 1 (Google Docs Viewer):** For DOCX/XLSX → attempt Google Docs Viewer iframe
   - `https://docs.google.com/gview?url=<absoluteUrl>&embedded=true`
   - **onload fires even when Google fails** — so onload only removes spinner
   - **8-second timeout is the SOLE Tier 2 trigger** — not onload
5. **Tier 2 (LibreOffice AJAX):** After 8 seconds, POST to `/budgets/api/convert-to-pdf/`
   - On success: show converted PDF in iframe
   - On failure: show download fallback
6. **Tier 3 (Download fallback):** Shows "Preview Unavailable" with download button

**Required DOM elements:**
- `#previewModal` — the modal overlay (hidden by default)
- `#previewContent` — container for preview content
- `#previewModalTitle` — optional title element
- `#previewSpinner` — dynamically created by `showLoading()`
- `#previewStatusMessage` — dynamically created by `showLoading()`

**Escape key:** Closes modal via `document.addEventListener('keydown', ...)`

### `static/js/htmx.min.js`
HTMX library for HTML-over-the-wire interactions. Used in some templates for dynamic partial updates.

---

## Modal Patterns

### Rejection Modal Pattern (Reference: `pr_detail.html`)

```html
<!-- Hidden modal div -->
<div id="prRejectModal" class="hidden fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
  <div class="bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden">
    <!-- Red header bar -->
    <div class="bg-gradient-to-r from-red-600 to-red-700 px-6 py-4">
      <h3 class="text-white font-bold text-lg">Reject Request</h3>
    </div>
    <!-- Form body -->
    <form method="POST" action="{% url 'admin_pr_action' pr.id %}">
      {% csrf_token %}
      <input type="hidden" name="action" value="reject">
      <div class="p-6">
        <label class="block text-sm font-semibold text-gray-700 mb-2">Reason for Rejection</label>
        <textarea name="rejection_reason" required minlength="10"
                  class="w-full border rounded-xl px-4 py-3 text-sm"
                  placeholder="Provide a detailed reason..."></textarea>
      </div>
      <div class="flex gap-3 px-6 pb-6">
        <button type="button" onclick="document.getElementById('prRejectModal').classList.add('hidden')"
                class="flex-1 bg-gray-100 ...">Cancel</button>
        <button type="submit" class="flex-1 bg-red-600 text-white ...">Confirm Rejection</button>
      </div>
    </form>
  </div>
</div>
```

**Key rules:**
- **Never use `confirm()` dialogs** — always use this modal pattern
- POST field name is always `rejection_reason` (standardized)
- `minlength="10"` on textarea
- Modal opened via `onclick="document.getElementById('...').classList.remove('hidden')"`
- Modal closed via `onclick="document.getElementById('...').classList.add('hidden')"`

### Preview Modal Pattern

```html
<div id="previewModal" class="hidden fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
  <div class="bg-white rounded-2xl shadow-2xl w-full max-w-5xl h-[85vh] flex flex-col overflow-hidden">
    <!-- Header with close button -->
    <div class="flex items-center justify-between px-6 py-4 border-b">
      <h3 id="previewModalTitle" class="font-bold text-lg text-gray-800">Document Preview</h3>
      <button onclick="closePreviewModal()" class="...">✕</button>
    </div>
    <!-- Content area -->
    <div id="previewContent" class="flex-1 overflow-hidden bg-gray-50"></div>
  </div>
</div>
```

---

## Pagination UI Pattern (Reference: `realignment_history.html`)

### Single Paginator
```html
{% if page_obj.has_other_pages %}
<nav class="flex items-center justify-between mt-6 px-4">
  <!-- Previous button -->
  {% if page_obj.has_previous %}
    <a href="?page={{ page_obj.previous_page_number }}" class="...">Previous</a>
  {% endif %}
  <!-- Page numbers -->
  {% for num in page_obj.paginator.page_range %}
    <a href="?page={{ num }}" class="{% if page_obj.number == num %}bg-blue-600 text-white{% endif %}">{{ num }}</a>
  {% endfor %}
  <!-- Next button -->
  {% if page_obj.has_next %}
    <a href="?page={{ page_obj.next_page_number }}" class="...">Next</a>
  {% endif %}
</nav>
{% endif %}
```

### Dual Paginator (`purchase_request_list.html`)
Two independent paginators using separate GET params (`pr_page` and `ad_page`). Each link must preserve the other paginator's state:

```html
<!-- PR table pagination -->
<a href="?pr_page={{ page_obj_pr.next_page_number }}&ad_page={{ page_obj_ad.number }}">Next</a>

<!-- AD table pagination -->
<a href="?ad_page={{ page_obj_ad.next_page_number }}&pr_page={{ page_obj_pr.number }}">Next</a>
```

**Critical:** Both GET params must be preserved in every pagination link to prevent the other paginator from resetting to page 1.

---

## Tailwind CSS Usage

- **No custom CSS files** — all styling is Tailwind utility classes
- Tailwind is managed via `django_tailwind_cli` in JIT mode
- Input: `static/css/input.css`
- Output: `css/output.css`
- Common patterns: `bg-gradient-to-r`, `rounded-2xl`, `shadow-2xl`, glassmorphism effects

---

## Template Inheritance

- Templates use `{% extends %}` and `{% block %}` for layout inheritance
- Base templates exist in the `templates/` directory at project root
- Each app's templates use app-specific base layouts
- `{% load static %}` is used in templates that reference JS/CSS files
- `{% load humanize %}` used for number formatting (intcomma)
