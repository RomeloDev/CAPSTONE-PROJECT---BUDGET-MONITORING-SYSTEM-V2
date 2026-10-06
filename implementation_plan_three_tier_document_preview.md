# Implementation Plan — 3-Tier Document Preview System

## Architecture

```
User clicks Preview
       ↓
   Pre-check: converted_pdf exists? → YES → Native PDF iframe (instant)
       ↓ NO
   File is PDF? → Native iframe
   File is image? → Native <img>
   File is DOCX/XLSX/other? → Start Tier 1
       ↓
   Tier 1: Google Docs Viewer (8s timeout)
       ↓ FAIL
   Tier 2: AJAX → LibreOffice conversion (lazy, on-demand)
       ↓ FAIL  
   Tier 3: Error card + Download button
```

---

## Model Audit — Fields Needed

### New fields to add (3 fields, 1 migration):

| Model | New Field | `upload_to` |
|---|---|---|
| `DepartmentPRE` | `uploaded_excel_pdf` | `pre_converted_pdfs/%Y/%m/` |
| `PurchaseRequest` | `uploaded_document_pdf` | `pr_converted_pdfs/%Y/%m/` |
| `ActivityDesign` | `uploaded_document_pdf` | `ad_converted_pdfs/%Y/%m/` |

### Existing `converted_pdf` fields (already in DB, no migration needed):

| Model | Field | Line |
|---|---|---|
| `DepartmentPRESupportingDocument` | `converted_pdf` | L2038 |
| `PurchaseRequestSupportingDocument` | `converted_pdf` | L1894 |
| `ActivityDesignSupportingDocument` | `converted_pdf` | L2247 |
| `BudgetRealignmentSupportingDocument` | `converted_pdf` | L3166 |
| `PurchaseRequestApprovedDocument` | `converted_pdf` | L1972 |
| `ActivityDesignApprovedDocument` | `converted_pdf` | L2325 |

### Excluded (no preview on drafts, per C6):
- ~~PREDraftSupportingDocument~~
- ~~PRDraftSupportingDocument~~

### `SupportingDocument` (ApprovedBudget docs):
Has no `converted_pdf` field. The approved_budget template only shows download links — no preview modal. **Add the field** so the AJAX endpoint can serve it if preview is added later. Total migration: **4 fields**.

---

## Settings

#### [MODIFY] `config/settings.py`
```python
LIBREOFFICE_PATH = os.getenv('LIBREOFFICE_PATH', r'C:\Program Files\LibreOffice\program\soffice.exe')
```

---

## Step 1 — Utility Function

#### [MODIFY] `apps/budgets/utils.py`

Add `convert_to_pdf_with_libreoffice(input_path)` — returns `bytes | None`.

Key properties:
- Uses `tempfile.TemporaryDirectory()` as output dir (C1 — no collision)
- `subprocess.CREATE_NO_WINDOW` on Windows (C2a — no console flash)
- `shutil.which('soffice')` with settings fallback (C2b — cross-platform)
- 60-second timeout
- Returns bytes (not path) since temp dir is cleaned up
- Never raises — logs errors, returns `None`

Also add helper:
```python
def attach_converted_pdf(instance, source_field, pdf_field):
    """Convert and save PDF onto instance. Fails silently."""
```

---

## Step 2 — AJAX Endpoint

### Placement decision

The `budgets` app has an empty `views.py` and no `urls.py`. Since the endpoint serves both admin and end-user panels, it belongs in the shared `budgets` app.

#### [NEW] `apps/budgets/urls.py`
```python
from django.urls import path
from . import views
urlpatterns = [
    path('api/convert-to-pdf/', views.convert_document_to_pdf, name='convert_to_pdf'),
]
```

#### [MODIFY] `config/urls.py` — add include
```python
path('budgets/', include('apps.budgets.urls')),
```
Final URL: `POST /budgets/api/convert-to-pdf/`

#### [MODIFY] `apps/budgets/views.py`

```python
@login_required
@require_POST
def convert_document_to_pdf(request):
    """
    AJAX endpoint for lazy LibreOffice PDF conversion (Tier 2).
    
    Request body (JSON):
        document_id: str (UUID or int)
        document_type: str (model identifier from whitelist)
    
    Response (JSON):
        { success: true, pdf_url: "/media/..." }
        { success: false, error: "..." }
    """
```

### Document type whitelist + model/field mapping:

| `document_type` value | Model class | Source field | PDF field |
|---|---|---|---|
| `pre_supporting_doc` | `DepartmentPRESupportingDocument` | `document` | `converted_pdf` |
| `pr_supporting_doc` | `PurchaseRequestSupportingDocument` | `document` | `converted_pdf` |
| `ad_supporting_doc` | `ActivityDesignSupportingDocument` | `document` | `converted_pdf` |
| `br_supporting_doc` | `BudgetRealignmentSupportingDocument` | `document` | `converted_pdf` |
| `pr_approved_doc` | `PurchaseRequestApprovedDocument` | `document` | `converted_pdf` |
| `ad_approved_doc` | `ActivityDesignApprovedDocument` | `document` | `converted_pdf` |
| `pre_main` | `DepartmentPRE` | `uploaded_excel_file` | `uploaded_excel_pdf` |
| `pr_main` | `PurchaseRequest` | `uploaded_document` | `uploaded_document_pdf` |
| `ad_main` | `ActivityDesign` | `uploaded_document` | `uploaded_document_pdf` |
| `budget_supporting_doc` | `SupportingDocument` | `document` | `converted_pdf` |

### Endpoint logic:
1. Parse JSON body, validate `document_type` against whitelist
2. Look up model instance by `document_id`
3. If `converted_pdf` already exists → return `{ success: true, pdf_url }` immediately
4. Call `convert_to_pdf_with_libreoffice(source_field.path)`
5. On success → save bytes to `converted_pdf` field, return URL
6. On failure → return `{ success: false, error: "Conversion failed" }`

### Security:
- `@login_required` — unauthenticated users get 302
- `@require_POST` — GET blocked
- Whitelist validation — unknown `document_type` returns 400
- No filesystem paths exposed in response
- CSRF token required (Django default for POST)

---

## Step 3 — Signals (Orphaned PDF Cleanup)

#### [MODIFY] `apps/budgets/signals.py`

Add `post_delete` handlers for all models with converted PDF fields.

**8 models to cover** (4 new fields + 4 existing):

```python
# Pattern for each:
@receiver(post_delete, sender=ModelClass)
def cleanup_model_pdf(sender, instance, **kwargs):
    for field_name in ['converted_pdf']:  # or 'uploaded_document_pdf', etc.
        field = getattr(instance, field_name, None)
        if field:
            field.delete(save=False)
```

`apps/budgets/apps.py` already imports `signals` in `ready()` — no changes needed.

---

## Step 4 — Shared Preview JS

### Decision: shared static JS file

The project has `static/js/` with only `htmx.min.js`. A new shared file avoids duplicating 80+ lines across 8 templates.

#### [NEW] `static/js/document-preview.js`

Contains two components:

### Component 1: `PreviewState` — Loading state manager

```javascript
const PreviewState = {
    _timeout: null,
    _abortController: null,

    showLoading(message) {
        // Show spinner + message in #previewContent area
        // Hide iframe/image if visible
    },
    updateMessage(message) {
        // Update the status text below spinner without re-rendering
    },
    showIframe(url) {
        // Hide spinner, inject <iframe src="url">
    },
    showImage(url) {
        // Hide spinner, inject <img src="url">
    },
    showError(originalUrl) {
        // Hide spinner, show error card with Download button
    },
    reset() {
        // Called on modal close
        // Clear timeout, abort any in-flight AJAX
        if (this._timeout) clearTimeout(this._timeout);
        if (this._abortController) this._abortController.abort();
    }
};
```

### Component 2: `openPreview()` — 3-tier preview function

```javascript
function openPreview(originalUrl, convertedPdfUrl, docId, docType) {
    // Show modal, initialize PreviewState
    const modal = document.getElementById('previewModal');
    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';

    // PRE-CHECK: Already converted? → instant native iframe
    if (convertedPdfUrl) {
        PreviewState.showIframe(convertedPdfUrl);
        return;
    }

    const ext = originalUrl.split('?')[0].split('.').pop().toLowerCase();

    // PDF → native iframe
    if (ext === 'pdf') {
        PreviewState.showIframe(originalUrl);
        return;
    }

    // Image → native <img>
    if (['jpg','jpeg','png','gif','webp'].includes(ext)) {
        PreviewState.showImage(originalUrl);
        return;
    }

    // DOCX/XLSX/other → Tier 1: Google Docs Viewer
    PreviewState.showLoading('Loading preview...');
    
    const gviewUrl = `https://docs.google.com/gview?url=${encodeURIComponent(
        window.location.origin + originalUrl
    )}&embedded=true`;

    const iframe = document.createElement('iframe');
    iframe.className = 'w-full h-full border-0';
    iframe.style.display = 'none';
    iframe.src = gviewUrl;

    // 8-second timeout → Tier 2
    PreviewState._timeout = setTimeout(() => {
        PreviewState.updateMessage('Google Docs unavailable. Generating local preview...');
        triggerTier2(originalUrl, docId, docType);
    }, 8000);

    iframe.onload = () => {
        try {
            // Cross-origin → catch blocks → assume GDocs loaded
            const body = iframe.contentDocument?.body;
            if (body && body.innerHTML.trim().length > 100) {
                clearTimeout(PreviewState._timeout);
                iframe.style.display = '';
                PreviewState.showLoading = () => {}; // no-op, already loaded
                // Replace content area with iframe
                document.getElementById('previewContent').innerHTML = '';
                document.getElementById('previewContent').appendChild(iframe);
            }
        } catch(e) {
            // Cross-origin security error — GDocs loaded successfully
            clearTimeout(PreviewState._timeout);
            iframe.style.display = '';
            document.getElementById('previewContent').innerHTML = '';
            document.getElementById('previewContent').appendChild(iframe);
        }
    };
    
    document.getElementById('previewContent').appendChild(iframe);
}

function triggerTier2(originalUrl, docId, docType) {
    // Tier 2: AJAX LibreOffice conversion
    PreviewState.updateMessage('Converting document, please wait...');

    PreviewState._abortController = new AbortController();

    fetch('/budgets/api/convert-to-pdf/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({ document_id: docId, document_type: docType }),
        signal: PreviewState._abortController.signal,
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            PreviewState.showIframe(data.pdf_url);
        } else {
            PreviewState.showError(originalUrl);
        }
    })
    .catch(err => {
        if (err.name !== 'AbortError') {
            PreviewState.showError(originalUrl);
        }
    });
}

function closePreviewModal() {
    PreviewState.reset();
    const modal = document.getElementById('previewModal');
    modal.classList.add('hidden');
    document.getElementById('previewContent').innerHTML = '';
    document.body.style.overflow = 'auto';
}

function getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value 
        || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
}
```

### Loading indicator UI (inside `PreviewState.showLoading`):

```html
<div class="flex flex-col items-center justify-center h-full gap-4">
    <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
    <p id="previewStatusMessage" class="text-sm font-medium text-gray-600">Loading preview...</p>
</div>
```

---

## Step 5 — Template Changes (8 templates)

Each template needs:
1. Include the shared JS file: `<script src="{% static 'js/document-preview.js' %}"></script>`
2. Replace current preview function with calls to `openPreview()`
3. Update preview buttons to pass `docId` and `docType` params
4. Ensure a CSRF token is available in the page (already present in all forms)
5. Standardize modal HTML structure with `previewContent` container

### Button change pattern:

**Before:**
```html
<button onclick="openAdminPreview('{{ doc.document.url }}', '{{ doc.file_name }}')">
```

**After:**
```html
<button onclick="openPreview(
    '{{ doc.document.url }}',
    '{% if doc.converted_pdf %}{{ doc.converted_pdf.url }}{% endif %}',
    '{{ doc.id }}',
    'ad_supporting_doc'
)">Preview</button>
```

### Template-specific `docType` values:

| Template | Document context | `docType` value |
|---|---|---|
| `admin/pr_detail.html` | PR supporting docs | `pr_supporting_doc` |
| | PR main document | `pr_main` |
| | PR signed/approved docs | `pr_approved_doc` |
| `admin/pre_detail.html` | PRE main Excel | `pre_main` |
| | PRE supporting docs | `pre_supporting_doc` |
| `admin/view_ad_detail.html` | AD main document | `ad_main` |
| | AD supporting docs | `ad_supporting_doc` |
| | AD signed docs | `ad_approved_doc` |
| `admin/pre_budget_realignment_detail.html` | Realignment supporting docs | `br_supporting_doc` |
| `end_user/view_pr_detail.html` | PR docs | `pr_supporting_doc`, `pr_main` |
| `end_user/view_pre_detail.html` | PRE docs | `pre_main`, `pre_supporting_doc` |
| `end_user/view_ad_detail.html` | AD docs | `ad_main`, `ad_supporting_doc` |
| `end_user/preview_realignment_documents.html` | Realignment docs | `br_supporting_doc` |

### Inline iframe templates (realignment):
`admin/pre_budget_realignment_detail.html` and `end_user/preview_realignment_documents.html` currently use inline `<iframe>` tags in Django HTML. These will be replaced with clickable Preview buttons that call `openPreview()`, plus a shared modal block appended to the template.

---

## Step 6 — Models

#### [MODIFY] `apps/budgets/models.py`

Add 4 nullable FileFields:
1. `SupportingDocument.converted_pdf` (after L144)
2. `DepartmentPRE.uploaded_excel_pdf` (after L419)
3. `PurchaseRequest.uploaded_document_pdf` (after L723)
4. `ActivityDesign.uploaded_document_pdf` (after L1031)

#### [NEW] Migration via `makemigrations`

---

## Execution Order

1. `config/settings.py` — add `LIBREOFFICE_PATH`
2. `apps/budgets/utils.py` — utility function + helper
3. `apps/budgets/models.py` — add 4 fields
4. `makemigrations` + `migrate`
5. `apps/budgets/signals.py` — add 8 cleanup handlers
6. `apps/budgets/views.py` — AJAX endpoint
7. `apps/budgets/urls.py` — new file with route
8. `config/urls.py` — include budgets URLs
9. `static/js/document-preview.js` — shared JS file
10. 8 templates — update buttons + include shared JS

**No view injection points in end_user/admin views** — conversion is now lazy (AJAX on-demand), not at upload time.

---

## Verification Plan

### Tier 1 — Google Docs (internet available)
1. Upload DOCX → click Preview → Google Docs renders in iframe within 8s ✅
2. Subsequent preview of same doc → still uses Google Docs (no `converted_pdf` yet) ✅

### Tier 1 → Tier 2 fallback (no internet / private LAN)
3. Disconnect internet → upload DOCX → click Preview → spinner shows "Loading preview..."
4. After 8s → message changes to "Converting document, please wait..."
5. LibreOffice converts → PDF iframe appears → `converted_pdf` saved to DB ✅
6. Click Preview again on same doc → `converted_pdf` exists → instant PDF iframe (skips Tiers 1+2) ✅

### Tier 2 → Tier 3 fallback (LibreOffice not installed)
7. Set `LIBREOFFICE_PATH` to invalid path → upload DOCX → click Preview
8. Tier 1 fails (no internet) → Tier 2 fails (bad path) → error card + Download button ✅

### Native types (no tiers involved)
9. Upload PDF → click Preview → native iframe immediately ✅
10. Upload JPG/PNG → click Preview → native `<img>` immediately ✅

### Cleanup
11. Delete a supporting document record → verify converted PDF file removed from disk ✅

### Modal UX
12. Click Preview → while spinner is showing → click Close → timeout/AJAX cancelled ✅
13. Close button accessible during all loading states ✅

---

## Open Questions

> [!NOTE]
> **Google Docs Viewer URL construction:** The `gviewUrl` needs a **publicly reachable** URL. When the server is on a campus LAN (e.g. `http://192.168.1.100/media/...`), Google's servers cannot fetch the file. In this scenario, Tier 1 will always timeout and Tier 2 will always be the effective primary. This is the intended behavior — Tier 1 is a "free optimization" when internet + public URL are available, not a requirement.
