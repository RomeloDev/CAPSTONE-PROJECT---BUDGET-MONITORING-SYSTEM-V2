# CONVENTIONS

Every established convention in this codebase, documented for consistent future development.

---

## Authentication and Roles

- `is_staff=True` is the admin role flag — gates access to `admin_panel` views
- `create_admin()` sets both `is_admin=True` and `is_staff=True`
- `User.save()` enforces: `if self.is_admin: self.is_staff = True`
- `is_approving_officer=True` marks physical document signers (no special web access)
- **Admin views:** Use `LoginRequiredMixin` + `UserPassesTestMixin` with `test_func` returning `self.request.user.is_staff`
- **End user views:** Use `@login_required` decorator or `LoginRequiredMixin`
- `USERNAME_FIELD = "email"` — users log in with email, not username

---

## Rejection Pattern

- **POST field name:** `rejection_reason` — standardized across all workflows. Never use `reason` or any other field name.
- **Fallback default:** `request.POST.get('rejection_reason', '')` — empty string, not `'Admin Rejected'`
- **Modal requirements:**
  - `<textarea name="rejection_reason" minlength="10" required>`
  - Hidden `<input type="hidden" name="action" value="reject">`
  - `{% csrf_token %}` inside the form
  - Red header bar (`bg-gradient-to-r from-red-600 to-red-700`)
  - Cancel button closes modal via `classList.add('hidden')`
- **Admin display:** Red card appears when `status == 'Rejected'` and `rejection_reason` is non-empty
- **End user display:** Rejection banner with full reason text
- **Never use `confirm()` dialogs** — always use the modal pattern above

---

## Document Conversion

### Functions in `budgets/utils.py`

```python
convert_to_pdf_with_libreoffice(input_path)
# Returns: PDF file contents as bytes, or None on failure
# Never raises — logs errors and returns None

attach_converted_pdf(instance, source_field_name, pdf_field_name)
# Converts source field → PDF and saves to pdf_field on the model instance
# Fails silently — logs errors but never raises
```

### Key implementation details

- `LIBREOFFICE_PATH` configurable via `.env` → `settings.LIBREOFFICE_PATH`
- Default: `r'C:\Program Files\LibreOffice\program\soffice.exe'`
- PATH lookup first via `shutil.which('soffice')`, then settings fallback
- `CREATE_NO_WINDOW` flag (`subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0`) — **required on Windows** to prevent console window flash
- `tempfile.TemporaryDirectory()` used to avoid filename collisions between concurrent conversions
- 60-second timeout on subprocess
- Conversion is **lazy** — triggered on first preview request (AJAX Tier 2), not at upload time
- `PDF_CONVERTIBLE = {'docx', 'doc', 'xlsx', 'xls', 'pptx', 'ppt', 'odt', 'ods'}`
- `IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}`

---

## File Cleanup

### `post_delete` signals in `budgets/signals.py`

Every model with a `converted_pdf` (or equivalent) field has a `post_delete` signal handler that deletes the file from disk:

```python
@receiver(post_delete, sender=ModelClass)
def cleanup_handler(sender, instance, **kwargs):
    if instance.converted_pdf:
        instance.converted_pdf.delete(save=False)
```

**Pattern:** Always use `field.delete(save=False)` — the `save=False` prevents a `.save()` call on a deleted instance.

**Models covered (10 handlers):**
1. `DepartmentPRE` → `uploaded_excel_pdf`
2. `PurchaseRequest` → `uploaded_document_pdf`
3. `ActivityDesign` → `uploaded_document_pdf`
4. `DepartmentPRESupportingDocument` → `converted_pdf`
5. `PurchaseRequestSupportingDocument` → `converted_pdf`
6. `ActivityDesignSupportingDocument` → `converted_pdf`
7. `BudgetRealignmentSupportingDocument` → `converted_pdf`
8. `PurchaseRequestApprovedDocument` → `converted_pdf`
9. `ActivityDesignApprovedDocument` → `converted_pdf`
10. `SupportingDocument` → `converted_pdf`

Additionally, `BudgetAllocation` has `post_delete` and `post_save` handlers for syncing `ApprovedBudget.remaining_budget`.

---

## AJAX Endpoint Conventions

- `@login_required` + `@require_POST` on all AJAX views
- `document_type` validated against the `DOCUMENT_TYPE_MAP` whitelist before any database lookup
- **Never expose filesystem paths in JSON responses** — only return URL paths (e.g., `/media/...`)
- CSRF token obtained via:
  1. `document.querySelector('[name=csrfmiddlewaretoken]')` — hidden input
  2. `document.cookie.match(/csrftoken=([^;]+)/)` — cookie fallback
- Request body is JSON (`Content-Type: application/json`)
- Response is always JSON: `{ "success": true/false, "pdf_url": "..." }` or `{ "success": false, "error": "..." }`

---

## Pagination Conventions

- **Page size:** 10 for all data tables
- **Single paginator:** GET param `page` (e.g., `realignment_history.html`, `department_pre_page.html`)
- **Dual paginators:** Separate GET params `pr_page` and `ad_page` (e.g., `purchase_request_list.html`)
- **Always preserve other GET params in pagination links** — prevents one paginator from resetting the other
- **TemplateView:** Use `Paginator` manually in `get_context_data()`:
  ```python
  paginator = Paginator(queryset, 10)
  page_number = self.request.GET.get('page')
  page_obj = paginator.get_page(page_number)
  context['page_obj'] = page_obj
  ```
- **ListView:** Use `paginate_by = 10`
- **Reference implementation:** `realignment_history.html` for single, `purchase_request_list.html` for dual
- **Count badges:** Use `{{ page_obj.paginator.count }}` not `{{ queryset|length }}` — the former gives total count, the latter gives current page count

---

## Storage

- **Local file storage:** `STORAGES["default"] = FileSystemStorage`
- `MEDIA_ROOT = BASE_DIR / 'media'`
- `MEDIA_URL = '/media/'`
- `X_FRAME_OPTIONS = 'SAMEORIGIN'` — **required for iframe document previews**. Do not set to `DENY`.
- `DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800` (50 MB)
- `FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800` (50 MB)
- Media files served by Nginx directly in production (not through Django)
- Static files served by WhiteNoise (`CompressedManifestStaticFilesStorage`)

---

## Archive Pattern

All major models have a standard set of archive fields:
- `is_archived = BooleanField(default=False, db_index=True)`
- `archived_at = DateTimeField(null=True, blank=True)`
- `archived_by = FK(User, SET_NULL, null=True, blank=True)`
- `archive_reason = TextField(blank=True)`
- `archive_type = CharField(choices=['FISCAL_YEAR', 'MANUAL'])`

Two managers:
- `objects = ArchiveManager()` — default manager that excludes `is_archived=True`
- `all_objects = models.Manager()` — includes everything

---

## Email Notifications

- **Module:** `apps/budgets/notifications.py`
- **Functions:** `notify_admins_new_request()`, `notify_user_status_change()`
- **Pattern:** Fire-and-forget — failures logged but never bubble up to caller
- **Admin emails:** Queried from `User.objects.filter(is_staff=True, is_active=True)`
- **Gmail SMTP:** Configured via `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` (App Password)

---

## Things That Must Never Be Done

1. **Never use `confirm()` dialogs** — always use the modal pattern
2. **Never hardcode `'Admin Rejected'` as rejection fallback** — use empty string `''`
3. **Never store `converted_pdf` paths for models without preview UI** — only add to models in the `DOCUMENT_TYPE_MAP`
4. **Never use CDN links for JS** — all JS must be in `static/js/`
5. **Never expose LibreOffice file paths in API responses** — only return URL paths
6. **Never run LibreOffice conversion at upload time** — lazy conversion only (on first preview)
7. **Never add model fields for future features not yet built** — avoid speculative fields
8. **Never set `X_FRAME_OPTIONS = 'DENY'`** — must be `SAMEORIGIN` for iframe previews
9. **Never filter drafts in templates** — always exclude in the queryset to avoid corrupting pagination counts
10. **Never use `{{ queryset|length }}` for pagination counts** — use `{{ page_obj.paginator.count }}`
