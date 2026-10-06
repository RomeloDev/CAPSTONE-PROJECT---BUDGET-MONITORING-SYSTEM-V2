# Implementation Plan — LibreOffice PDF Conversion for Document Preview

## Summary

All non-PDF/non-image user-uploaded files (DOCX, XLSX, etc.) will be converted to PDF immediately after the file record is saved in the view. The preview modal then renders the converted PDF natively in the browser — no external services, no client-side JS libraries, works fully on a private LAN.

---

## Model Audit — `converted_pdf` Field Status

After reading `apps/budgets/models.py` in full:

| Model | File Field(s) That Accept DOCX/XLSX | `converted_pdf` exists? | Action |
|---|---|---|---|
| `PREDraftSupportingDocument` | `document` (pdf, docx, doc, xlsx, xls, jpg, png) | ❌ No | Add field |
| `DepartmentPRESupportingDocument` | `document` (pdf, docx, doc, xlsx, xls, jpg, png) | ✅ Yes (line 2038) | None |
| `DepartmentPREApprovedDocument` | `document` (pdf, jpg, jpeg, png only) | ❌ No | **Skip** — accepts PDF/image only, no conversion needed |
| `PRDraftSupportingDocument` | `document` (no extension validation) | ❌ No | Add field |
| `PurchaseRequestSupportingDocument` | `document` (no extension validation) | ✅ Yes (line 1894) | None |
| `PurchaseRequestApprovedDocument` | `document` (pdf, jpg, jpeg, png only) | ✅ Yes (line 1972) — but unnecessary | **Skip** — accepts PDF/image only |
| `ActivityDesignSupportingDocument` | `document` (no extension validation) | ✅ Yes (line 2247) | None |
| `ActivityDesignApprovedDocument` | `document` (pdf, jpg, jpeg, png only) | ✅ Yes (line 2325) — but unnecessary | **Skip** — accepts PDF/image only |
| `BudgetRealignmentSupportingDocument` | `document` (pdf, docx, doc, xlsx, xls, jpg, png) | ✅ Yes (line 3166) | None |
| `ActivityDesign` (parent) | `uploaded_document` (docx, doc only) | ❌ No | Add field — **critical**, this is the primary AD document shown in the preview panel |
| `PurchaseRequest` (parent) | `uploaded_document` (docx, doc, pdf) | ❌ No | Add field — needed for PR upload-based submissions |
| `DepartmentPRE` (parent) | `uploaded_excel_file` (xlsx, xls only) | ❌ No | Add field — needed for Excel preview |

**Draft models** (`PREDraft`, `PRDraft`, `ADDraft`) store temporary files before submission. These drafts are deleted after submission, so the converted PDF only needs to be on the **submitted** model (the supporting document copy). However, during the draft upload step the user sees a preview — so draft supporting docs also need conversion.

---

## New `converted_pdf` Fields to Add (Migration Required)

### Models needing new fields:
1. **`PREDraftSupportingDocument`** — `converted_pdf = FileField(upload_to='pre_draft_docs_pdf/%Y/%m/', null=True, blank=True)`
2. **`PRDraftSupportingDocument`** — `converted_pdf = FileField(upload_to='pr_draft_docs_pdf/%Y/%m/', null=True, blank=True)`
3. **`ActivityDesign`** — `uploaded_document_pdf = FileField(upload_to='ad_converted_pdfs/%Y/%m/', null=True, blank=True)` (named `uploaded_document_pdf` to avoid collision with `original_ad_pdf`)
4. **`PurchaseRequest`** — `uploaded_document_pdf = FileField(upload_to='pr_converted_pdfs/%Y/%m/', null=True, blank=True)`
5. **`DepartmentPRE`** — `uploaded_excel_pdf = FileField(upload_to='pre_converted_pdfs/%Y/%m/', null=True, blank=True)`

> [!NOTE]
> All are `null=True, blank=True` — no migration data fill required. One migration file covers all 5 changes.

---

## Settings & Environment

Add to `.env`:
```
LIBREOFFICE_PATH=C:\Program Files\LibreOffice\program\soffice.exe
```

Add to `config/settings.py`:
```python
LIBREOFFICE_PATH = os.getenv('LIBREOFFICE_PATH', r'C:\Program Files\LibreOffice\program\soffice.exe')
```

---

## Proposed Changes

### Step 1 — Utility Function

#### [MODIFY] `apps/budgets/utils.py`

Add `convert_to_pdf_with_libreoffice(input_path)`:

```python
import subprocess, os, logging, traceback
from pathlib import Path
from django.conf import settings

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
PDF_CONVERTIBLE   = {'docx', 'doc', 'xlsx', 'xls', 'pptx', 'ppt', 'odt', 'ods'}

def convert_to_pdf_with_libreoffice(input_path: str) -> str | None:
    """
    Convert a file to PDF using LibreOffice headless mode.
    
    Returns the absolute path to the generated PDF on success,
    or None on failure (logs but never raises).
    
    The PDF is placed in the same directory as the input file.
    """
    try:
        soffice = getattr(settings, 'LIBREOFFICE_PATH',
                          r'C:\Program Files\LibreOffice\program\soffice.exe')
        input_path = str(input_path)
        out_dir = str(Path(input_path).parent)
        
        result = subprocess.run(
            [soffice, '--headless', '--convert-to', 'pdf', '--outdir', out_dir, input_path],
            timeout=60,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"[LibreOffice] Conversion failed for {input_path}: {result.stderr}")
            return None
        
        pdf_path = str(Path(input_path).with_suffix('.pdf'))
        if not os.path.exists(pdf_path):
            logger.error(f"[LibreOffice] PDF not found after conversion: {pdf_path}")
            return None
        
        logger.info(f"[LibreOffice] Successfully converted: {input_path} → {pdf_path}")
        return pdf_path
    except subprocess.TimeoutExpired:
        logger.error(f"[LibreOffice] Conversion timed out for: {input_path}")
        return None
    except Exception:
        logger.error(f"[LibreOffice] Unexpected error:\n{traceback.format_exc()}")
        return None
```

Also add a helper used by views:
```python
def get_file_extension(filename: str) -> str:
    return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

def needs_conversion(filename: str) -> bool:
    return get_file_extension(filename) in PDF_CONVERTIBLE
```

---

### Step 2 — Models

#### [MODIFY] `apps/budgets/models.py`

Add 5 new nullable FileFields:

1. `PREDraftSupportingDocument.converted_pdf`
2. `PRDraftSupportingDocument.converted_pdf`
3. `ActivityDesign.uploaded_document_pdf`
4. `PurchaseRequest.uploaded_document_pdf`
5. `DepartmentPRE.uploaded_excel_pdf`

#### [NEW] Migration file

`apps/budgets/migrations/0012_add_converted_pdf_fields.py`

---

### Step 3 — Views (Injection Points)

The conversion is called **after** `obj.save()` in the view, never in the model.

The pattern is:
```python
from apps.budgets.utils import convert_to_pdf_with_libreoffice, needs_conversion
from django.core.files import File

def _attach_converted_pdf(obj, file_field_name, pdf_field_name, upload_subdir):
    """Save converted PDF back onto the model instance."""
    file_field = getattr(obj, file_field_name)
    if not file_field or not needs_conversion(file_field.name):
        return
    pdf_path = convert_to_pdf_with_libreoffice(file_field.path)
    if pdf_path:
        with open(pdf_path, 'rb') as f:
            getattr(obj, pdf_field_name).save(
                os.path.basename(pdf_path), File(f), save=True
            )
        os.remove(pdf_path)  # Remove the temp file from media root
```

#### Injection points (8 locations):

| View / Location | Model Created | Field Converted | `converted_pdf` field |
|---|---|---|---|
| `end_user_panel/views.py` ~L291 | `PREDraftSupportingDocument` | `document` | `converted_pdf` |
| `end_user_panel/views.py` ~L431 | `DepartmentPRESupportingDocument` | `document` | `converted_pdf` |
| `end_user_panel/views.py` ~L1334 | `PRDraftSupportingDocument` | `document` | `converted_pdf` |
| `end_user_panel/views.py` ~L1432 | `PurchaseRequestSupportingDocument` | `document` | `converted_pdf` |
| `end_user_panel/views.py` ~L1409 | `PurchaseRequest` (on submit) | `uploaded_document` | `uploaded_document_pdf` |
| `end_user_panel/views.py` ~L1725 | `ActivityDesignSupportingDocument` | `document` | `converted_pdf` |
| `end_user_panel/views.py` ~L1685/1713 | `ActivityDesign` (on AD submit) | `uploaded_document` | `uploaded_document_pdf` |
| `end_user_panel/views.py` ~L2189 | `BudgetRealignmentSupportingDocument` | `document` | `converted_pdf` |

> **Admin-side uploads** (`admin_panel/views.py` ~L269, ~L1889): Admin also uploads realignment and other supporting docs. These two admin injection points also need conversion.

---

### Step 4 — Templates (Preview Logic Update)

**8 templates**, same set as identified in Issue 1 audit. Replace all preview JS functions with unified 2-way logic:

```javascript
function openPreview(url, convertedPdfUrl, title) {
    // convertedPdfUrl: Django template passes {{ doc.converted_pdf.url }} or ''
    const previewUrl = convertedPdfUrl || url;
    const ext = url.split('?')[0].split('.').pop().toLowerCase();
    
    if (ext === 'pdf' || convertedPdfUrl) {
        // Native iframe
        container.innerHTML = `<iframe src="${previewUrl}" ...></iframe>`;
    } else if (['jpg','jpeg','png','gif','webp'].includes(ext)) {
        // Native img tag
        container.innerHTML = `<img src="${url}" .../>`;
    } else {
        // No conversion available — error card + download
        container.innerHTML = `...Preview unavailable... <a href="${url}" download>Download</a>`;
    }
}
```

In templates, the "Preview" button for a document record becomes:
```html
<button onclick="openPreview('{{ doc.document.url }}', '{% if doc.converted_pdf %}{{ doc.converted_pdf.url }}{% endif %}', '{{ doc.file_name }}')">
```

For the **parent model's main document** (`ad.uploaded_document`, `pr.uploaded_document`, `pre.uploaded_excel_file`):
```html
<button onclick="openPreview('{{ ad.uploaded_document.url }}', '{% if ad.uploaded_document_pdf %}{{ ad.uploaded_document_pdf.url }}{% endif %}', 'Main AD Document')">
```

**Templates to update:**

| Template | Current preview function | Update needed |
|---|---|---|
| `admin/pr_detail.html` | `openPreviewModal()` — no type check | Replace with 2-way logic |
| `admin/pre_detail.html` | `openGoogleDocsPreview()` — no type check | Replace with 2-way logic |
| `admin/view_ad_detail.html` | `openAdminPreview()` — partial check, DOCX → download | Replace `else` with error card (already has `converted_pdf` path) |
| `admin/pre_budget_realignment_detail.html` | Inline `<iframe>` per doc | Switch to button-triggered modal with 2-way logic |
| `end_user/view_pr_detail.html` | `openGoogleDocsPreview()` — encode/decode no-op | Replace with 2-way logic |
| `end_user/view_pre_detail.html` | Same broken pattern | Replace with 2-way logic |
| `end_user/view_ad_detail.html` | Same broken pattern | Replace with 2-way logic |
| `end_user/preview_realignment_documents.html` | Inline `<iframe>` per doc | Switch to conditional 2-way display |

---

## Execution Order

1. `apps/budgets/utils.py` — add utility function
2. `apps/budgets/models.py` — add 5 new fields
3. `python manage.py makemigrations budgets` — generate migration
4. `python manage.py migrate` — apply
5. `apps/end_user_panel/views.py` — inject conversion calls (8 points)
6. `apps/admin_panel/views.py` — inject conversion calls (2 points)
7. 8 templates — update preview JS to 2-way logic + pass `converted_pdf` URL

---

## Verification Plan

1. Upload a **DOCX** as PR supporting doc → verify `converted_pdf` file appears in `media/pr_supporting_docs_pdf/`
2. Upload an **XLSX** as PRE supporting doc → same check
3. Click **Preview** on a DOCX doc → iframe renders the PDF natively
4. Test with LibreOffice path missing/wrong → verify error card + Download button appears, no crash
5. Upload a PDF → no conversion attempted, preview works as before
6. Upload a JPG/PNG → no conversion attempted, `<img>` renders

---

## Open Questions

> [!IMPORTANT]
> **Realignment end-user upload (~L2160-2186):** This view already has image→PDF conversion via `Pillow`. After this change, that Pillow block becomes unnecessary for DOCX/XLSX because LibreOffice handles it. Should we **remove the Pillow conversion block** and unify everything through LibreOffice? Or keep Pillow for images and use LibreOffice only for Office files?

> [!NOTE]
> **Draft supporting docs:** `PREDraftSupportingDocument` and `PRDraftSupportingDocument` are temporary — they exist only until the user submits the form, at which point the files are re-linked to the submitted model's supporting document records. Should conversion also happen on the draft records (for preview during draft editing), or only on the final submitted supporting document records?
