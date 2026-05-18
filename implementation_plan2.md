# Implementation Plan — Issue 1 (Hybrid Preview) + Issue 2 (AD Rejection Modal)

## Summary

Two post-testing defects:

1. **Hybrid Preview** — Phase 2 removed Google Docs Viewer completely. The correct behaviour for DOCX/XLSX is to route through `docs.google.com/gview` (internet is available). PDF and images should stay native.

2. **AD Rejection Modal** — The `view_ad_detail.html` admin template still uses `confirm()` dialogs for both reject buttons. No `rejection_reason` textarea exists, so the view always saves the default string `'Admin Rejected'` instead of a real reason.

---

## Issue 1 — Hybrid Preview: Current State vs Required

### The correct 3-way logic (to be applied consistently everywhere)

```js
const ext = url.split('?')[0].split('.').pop().toLowerCase();
if (ext === 'pdf') {
    // Native browser iframe
} else if (['jpg','jpeg','png','gif','webp'].includes(ext)) {
    // Native <img> tag
} else {
    // Google Docs Viewer: https://docs.google.com/gview?url=<encoded>&embedded=true
}
```

### Audit of all 8 affected templates

| # | Template | Preview type | Current state | Fix needed? |
|---|---|---|---|---|
| 1 | `admin/pr_detail.html` | Modal — `openPreviewModal()` | Always sets `iframe.src = url` — no type check | ✅ Yes |
| 2 | `admin/pre_detail.html` | Modal — `openGoogleDocsPreview()` | Always sets `frame.src = url` — no type check | ✅ Yes |
| 3 | `admin/view_ad_detail.html` | Inline panel — `openAdminPreview()` | Has PDF+image checks, but DOCX → "Download" fallback | ✅ Yes (replace Download fallback with GDocs) |
| 4 | `admin/pre_budget_realignment_detail.html` | Inline `<iframe>` directly in HTML (no JS) | All types hardcoded to `<iframe src="...">` — DOCX/XLSX will fail silently | ✅ Yes — needs JS-driven hybrid or template-level type check |
| 5 | `end_user/view_pr_detail.html` | Modal — `openGoogleDocsPreview()` | Encodes+immediately decodes URL, sends ALL types to plain iframe | ✅ Yes |
| 6 | `end_user/view_pre_detail.html` | Modal — `openGoogleDocsPreview()` | Same broken pattern as #5 | ✅ Yes |
| 7 | `end_user/view_ad_detail.html` | Modal — `openGoogleDocsPreview()` | Same broken pattern as #5 | ✅ Yes |
| 8 | `end_user/preview_realignment_documents.html` | Inline `<iframe>` per doc (no JS) | All hardcoded `<iframe src="...">` — DOCX/XLSX broken | ✅ Yes — needs type-aware display |

> **Templates 1–3 and 5–7:** The fix is to replace the JS function body with the 3-way logic above.
>
> **Templates 4 and 8:** These use inline `<iframe>` tags in Django template HTML (no JS modal). Fix is to wrap each `<iframe>` in a Django template conditional that checks the file extension.

---

## Issue 2 — AD Rejection Modal: Current State vs Required

### What is missing (compared to PR which is working)

| Item | PR (`pr_detail.html`) | AD (`view_ad_detail.html`) |
|---|---|---|
| Pending Reject button | Opens `#adRejectModal` with textarea | `confirm()` dialog — **missing** |
| Awaiting Verification Reject | Opens `#adVerifyRejectModal` with textarea | `confirm()` dialog — **missing** |
| Admin sidebar rejection reason display | ✅ Red card when `status == 'Rejected'` | **Missing** |
| End-user rejection banner | ✅ `view_pr_detail.html` shows reason | ✅ Already added in Phase 3 |
| View saves rejection_reason | ✅ From POST field `rejection_reason` | ⚠️ Saves POST field but defaults to `'Admin Rejected'` when field missing |

### Changes required for Issue 2

1. **`admin/view_ad_detail.html`** — Replace both `confirm()` reject buttons:
   - Pending stage Reject → trigger `#adRejectModal`
   - Awaiting Admin Verification stage Reject → trigger `#adVerifyRejectModal`
   - Add both modal HTML blocks (same pattern as `pr_detail.html`)
   - Add a rejection reason display card in the sidebar (when `status == 'Rejected'`)

2. **`admin_panel/views.py` line 1692** — Change fallback from `'Admin Rejected'` to `''` so empty submissions are valid (modal requires input anyway):
   ```python
   # Before:
   ad.rejection_reason = request.POST.get('rejection_reason', 'Admin Rejected')
   # After:
   ad.rejection_reason = request.POST.get('rejection_reason', '').strip()
   ```

---

## Proposed Changes

### Issue 1 — 8 templates

#### [MODIFY] `admin/pr_detail.html`
- Replace body of `openPreviewModal()`: add 3-way extension check.
- The modal has `id="previewFrame"` (single iframe) — for GDocs, set `iframe.src = gviewUrl`. For images, replace iframe with `<img>` injection. For PDF, keep `iframe.src = url`.

#### [MODIFY] `admin/pre_detail.html`
- Replace body of `openGoogleDocsPreview()`: same 3-way logic.

#### [MODIFY] `admin/view_ad_detail.html`
- Replace the `else` branch of `openAdminPreview()`: instead of "Download" fallback, inject an iframe pointing to GDocs viewer URL.

#### [MODIFY] `admin/pre_budget_realignment_detail.html`
- The inline `<iframe src="{{ doc.document.url }}">` renders at lines ~144. Add Django template conditionals:
  - If extension is `pdf` or image → keep `<iframe>` / `<img>`
  - Otherwise → wrap in an iframe pointing to GDocs viewer

#### [MODIFY] `end_user/view_pr_detail.html`
- Replace body of `openGoogleDocsPreview()`: the current encode→decode-and-set-plain-iframe is functionally a no-op wrapper — replace with proper 3-way logic.

#### [MODIFY] `end_user/view_pre_detail.html`
- Same fix as `view_pr_detail.html`.

#### [MODIFY] `end_user/view_ad_detail.html`
- Same fix as `view_pr_detail.html`.

#### [MODIFY] `end_user/preview_realignment_documents.html`
- Replace each hardcoded `<iframe src="...">` with a Django template conditional block (same approach as realignment_detail above).

---

### Issue 2 — 2 files

#### [MODIFY] `admin/view_ad_detail.html`
- **Pending stage:** Replace Reject `<button>` (with `confirm()`) with a trigger button that opens `#adRejectModal`.
- **Awaiting Verification stage:** Replace Reject `<button>` (with `confirm()`) with a trigger button that opens `#adVerifyRejectModal`.
- **Add modals** at end of file (same pattern as `pr_detail.html`'s `#prRejectModal`):
  - `#adRejectModal` — form POSTs to `handle_activity_design_request`, action=reject, has `rejection_reason` textarea (required, minlength=10).
  - `#adVerifyRejectModal` — same URL, action=reject, has `reason` textarea.
- **Add sidebar card** showing `ad.rejection_reason` when `ad.status == 'Rejected'`.

#### [MODIFY] `admin_panel/views.py`
- Line ~1692: change `'Admin Rejected'` fallback to `''`:
  ```python
  ad.rejection_reason = request.POST.get('rejection_reason', '').strip()
  ```

---

## Verification Plan

### After changes:
1. Upload a **PDF** → click Preview → should render natively in browser iframe ✅
2. Upload a **JPG/PNG** → click Preview → should render as `<img>` ✅
3. Upload a **DOCX** → click Preview → should open Google Docs Viewer iframe ✅
4. Upload an **XLSX** → click Preview → should open Google Docs Viewer iframe ✅
5. Reject an **AD** as admin → modal appears with required textarea ✅
6. Submit rejection with reason text → reason saved, displayed in admin sidebar card ✅
7. End user opens rejected AD → red banner shows the reason text ✅

Test all 4 template locations (admin PR, admin PRE, admin AD, admin Realignment) and all 4 end-user locations (view_pr, view_pre, view_ad, preview_realignment).

---

## Open Questions

> [!NOTE]
> **Template 4 & 8 approach:** `pre_budget_realignment_detail.html` and `preview_realignment_documents.html` use inline iframes in Django template HTML, not a JS modal system. For these, I'll use a Django template `{% with ext=doc.document.url|... %}` conditional, or a simpler JavaScript `onload` replacement — whichever is cleaner. Since these templates already have a "Download" link next to each iframe, the GDocs viewer approach gives the richest preview experience for DOCX/XLSX. Confirm this is acceptable.
