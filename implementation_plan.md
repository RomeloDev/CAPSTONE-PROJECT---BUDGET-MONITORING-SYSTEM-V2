# Budget Monitoring System — Production Readiness: Feature Implementation Plan

## Codebase Audit Summary

After a thorough analysis of the entire codebase, here is the current architecture:

| Component | Details |
|---|---|
| **Framework** | Django 5.2.8 with Tailwind CSS (JIT) |
| **Database** | SQLite (dev) / PostgreSQL (prod) via `dj-database-url` |
| **Storage** | Cloudinary (`RawMediaCloudinaryStorage`) — **20 FileField references** across models |
| **Static Files** | WhiteNoise for static, Cloudinary for media |
| **Auth** | Custom User model (`user_accounts.User`) with role flags (`is_admin`, `is_staff`, `is_approving_officer`) |
| **Email** | Gmail SMTP configured in `.env` but **never used** in app logic (only password reset via Django built-in) |
| **Apps** | `admin_panel`, `end_user_panel`, `budgets`, `user_accounts` |
| **Deployment** | Docker + Gunicorn, originally for Render (cloud) |

---

## Production Readiness Findings

> [!CAUTION]
> **Critical Security Issue**: The `.env` file contains **live Cloudinary API credentials** and a **Gmail App Password** in plaintext. Ensure `.env` is in `.gitignore` and never committed to version control.

> [!WARNING]
> **Google Docs Viewer Dependency**: The current document preview system uses `docs.google.com/gview` for rendering PDFs/documents — **13 template references**. On a campus-only network without internet access, this will completely break. We must implement a local preview solution.

> [!IMPORTANT]
> **Existing SystemNotification model**: The `budgets.models.SystemNotification` model already exists but is only used for in-app notifications. Email notifications will supplement this, not replace it.

---

## Feature 1: Rejection Comment Modal (Admin Panel — All Detail Pages)

### Scope
When admin clicks "Reject" on any request (PRE, PR, AD, Realignment), instead of a browser `confirm()` dialog, a styled modal appears where admin can type a rejection reason/comment. This comment is saved to the model's `rejection_reason` field and shown to the end user.

### Proposed Changes

---

#### [MODIFY] [pr_detail.html](file:///c:/Users/John%20Romel%20Lucot/OneDrive/Desktop/Capstone%20project/capstone-projectv2/apps/admin_panel/templates/admin_panel/pr_detail.html)

- **Remove** the inline `onclick="return confirm(...)"` from the Reject buttons (lines 415-418 and 494-497)
- **Add** a rejection comment modal (`<div id="rejectionModal">`) to the `{% block modals %}` section with:
  - Textarea for admin comments (required, min 10 characters)
  - Hidden input for the action type (`reject`)
  - Form submits to `{% url 'admin_pr_action' pr.id %}`
  - Cancel button to close modal
- **Wire** the Reject buttons to open the modal via JavaScript instead of `confirm()`

---

#### [MODIFY] [pre_detail.html](file:///c:/Users/John%20Romel%20Lucot/OneDrive/Desktop/Capstone%20project/capstone-projectv2/apps/admin_panel/templates/admin_panel/pre_detail.html)

- Same pattern as PR: replace `confirm()` with rejection modal
- PRE already handles `rejection_reason` in the `admin_handle_pre_action` view — just wire the modal to send `reason` POST field

---

#### [MODIFY] [departments_ad_request.html](file:///c:/Users/John%20Romel%20Lucot/OneDrive/Desktop/Capstone%20project/capstone-projectv2/apps/admin_panel/templates/admin_panel/departments_ad_request.html) & [view_ad_detail.html](file:///c:/Users/John%20Romel%20Lucot/OneDrive/Desktop/Capstone%20project/capstone-projectv2/apps/admin_panel/templates/admin_panel/view_ad_detail.html)

- AD reject already reads `rejection_reason` from POST (line 1673 in views.py) — add the same modal pattern

---

#### [MODIFY] [pre_budget_realignment_detail.html](file:///c:/Users/John%20Romel%20Lucot/OneDrive/Desktop/Capstone%20project/capstone-projectv2/apps/admin_panel/templates/admin_panel/pre_budget_realignment_detail.html)

- Add rejection modal for realignment requests

---

#### [MODIFY] [views.py (admin_panel)](file:///c:/Users/John%20Romel%20Lucot/OneDrive/Desktop/Capstone%20project/capstone-projectv2/apps/admin_panel/views.py)

- **`handle_pr_action`** (line 1409): Update reject branch to read `rejection_reason` from POST body (currently just sets status to Rejected with no reason captured)
- **`HandleADRequestView`** (line 1671): Already reads `rejection_reason` — no change needed
- **`admin_handle_pre_action`** (line 987): Already reads `reason` — just ensure template sends correctly

---

#### [NEW] Shared Rejection Modal Template Partial

Create `apps/admin_panel/templates/admin_panel/partials/_rejection_modal.html` — a reusable modal component that can be `{% include %}`d across all detail pages, accepting context variables like `form_action_url` and `request_identifier`.

---

#### End-User Visibility

#### [MODIFY] End-user detail templates

- [view_pr_detail.html](file:///c:/Users/John%20Romel%20Lucot/OneDrive/Desktop/Capstone%20project/capstone-projectv2/apps/end_user_panel/templates/end_user_panel/view_pr_detail.html)
- [view_pre_detail.html](file:///c:/Users/John%20Romel%20Lucot/OneDrive/Desktop/Capstone%20project/capstone-projectv2/apps/end_user_panel/templates/end_user_panel/view_pre_detail.html)
- [view_ad_detail.html](file:///c:/Users/John%20Romel%20Lucot/OneDrive/Desktop/Capstone%20project/capstone-projectv2/apps/end_user_panel/templates/end_user_panel/view_ad_detail.html)

Display the rejection reason when status is "Rejected" — styled as a red alert card.

---

## Feature 2: Gmail Email Notifications

### Scope
Send transactional emails via Gmail SMTP for two event types:
1. **To Admin(s)**: When a new request (PRE, PR, AD, Realignment) is submitted by an end user
2. **To End User**: When their request is Partially Approved, Approved, or Rejected

### Architecture Decision

> [!IMPORTANT]
> **Synchronous vs Asynchronous Email Sending**: Since this is a campus-only deployment without Celery/Redis infrastructure, we will use **Django's `send_mail()` wrapped in a try/except** directly in the view logic. If the email fails, the action still succeeds (email is best-effort). A `logging.error()` will capture failures for debugging. This is a pragmatic decision for a capstone project — production enterprise systems would use a task queue.

### Proposed Changes

---

#### [NEW] [notifications.py](file:///c:/Users/John%20Romel%20Lucot/OneDrive/Desktop/Capstone%20project/capstone-projectv2/apps/budgets/notifications.py)

Centralized notification service module with:

```python
# Core functions:
def notify_admin_new_request(request_type, request_obj)
def notify_user_status_change(request_type, request_obj, new_status, rejection_reason='')
```

- Uses `django.core.mail.send_mail()` with `fail_silently=True`
- Queries all `User.objects.filter(is_staff=True)` for admin email recipients
- Uses `request_obj.submitted_by.email` for end-user recipient
- HTML email bodies with the system branding

---

#### [NEW] Email Templates

Create HTML email templates for professional-looking notifications:
- `templates/emails/admin_new_request.html` — admin notification of new submission
- `templates/emails/user_status_update.html` — user notification of status change (approved/rejected)

---

#### [MODIFY] [views.py (admin_panel)](file:///c:/Users/John%20Romel%20Lucot/OneDrive/Desktop/Capstone%20project/capstone-projectv2/apps/admin_panel/views.py)

Add email notification calls at each status change point:

| View Function | Status Change | Email Target |
|---|---|---|
| `admin_handle_pre_action` (approve) | Pending → Partially Approved | End User |
| `admin_handle_pre_action` (reject) | Pending → Rejected | End User |
| `admin_verify_and_approve_pre` (approve) | Awaiting → Approved | End User |
| `handle_pr_action` (approve) | Pending → Partially Approved | End User |
| `handle_pr_action` (reject) | Pending → Rejected | End User |
| `admin_verify_and_approve_pr` (approve) | Awaiting → Approved | End User |
| `HandleADRequestView` (approve/reject/final) | Various | End User |
| `handle_admin_realignment_action` (approve/reject) | Various | End User |

---

#### [MODIFY] [views.py (end_user_panel)](file:///c:/Users/John%20Romel%20Lucot/OneDrive/Desktop/Capstone%20project/capstone-projectv2/apps/end_user_panel/views.py)

Add email notification calls when end users submit new requests:

| View/Function | Action | Email Target |
|---|---|---|
| PRE submission | New PRE submitted | Admin(s) |
| `purchase_request_upload` | New PR submitted | Admin(s) |
| `activity_design_upload` | New AD submitted | Admin(s) |
| Realignment submission | New Realignment submitted | Admin(s) |

---

#### [MODIFY] [settings.py](file:///c:/Users/John%20Romel%20Lucot/OneDrive/Desktop/Capstone%20project/capstone-projectv2/config/settings.py)

- Add `ADMIN_NOTIFICATION_EMAIL` setting (configurable via `.env`) for fallback admin email
- Add `SYSTEM_NAME` constant for email subject lines

---

## Feature 3: Local File Storage (Remove Cloudinary)

### Scope
Replace all Cloudinary storage with Django's default `FileSystemStorage` (local disk). Files stored under `MEDIA_ROOT` (`/app/media/` or `BASE_DIR / 'media'`).

> [!WARNING]
> **Breaking Change**: This migration requires all **existing files to be downloaded from Cloudinary** and re-uploaded to local storage, OR a fresh deployment with no existing data (since this is going to a new physical server, the latter is likely). Existing `db.sqlite3` will have Cloudinary URLs in FileField values that will become invalid.

### Impact Analysis — All `RawMediaCloudinaryStorage()` References

| Model | Field | Line | Upload Path |
|---|---|---|---|
| `SupportingDocument` | `document` | 135 | `approved_budgets/{year}/{format}/` |
| `PREDraft` | `uploaded_excel_file` | 345 | `pre_drafts/%Y/%m/` |
| `PREDraftSupportingDocument` | `document` | 371 | `pre_draft_docs/%Y/%m/` |
| `DepartmentPRE` | `uploaded_excel_file` | 419 | `pre_uploads/%Y/%m/` |
| `PurchaseRequest` | `uploaded_document` | 723 | `pr_documents/%Y/%m/` |
| `ActivityDesign` | `uploaded_document` | 1035 | `ad_uploads/%Y/%m/` |
| `PRDraft` | `pr_file` | 1826 | `pr_drafts/%Y/%m/` |
| `PRDraftSupportingDocument` | `document` | 1856 | `pr_draft_supporting/%Y/%m/` |
| `PurchaseRequestSupportingDocument` | `document` | 1880 | `pr_supporting_docs/%Y/%m/` |
| `PurchaseRequestApprovedDocument` | `document` | 1950 | `pr_signed_docs/` |
| `DepartmentPRESupportingDocument` | `document` | 2029 | `pre_supporting_docs/%Y/%m/` |
| `DepartmentPREApprovedDocument` | `document` | ~2238 | `pre_signed_docs/` |
| `ActivityDesignSupportingDocument` | `document` | ~2856+ | `ad_supporting_docs/%Y/%m/` |
| `PREBudgetRealignment` | `partially_approved_pdf` | 2856 | `br_pdfs/%Y/%m/` |
| `PREBudgetRealignment` | `approved_documents` | 2863 | `br_approved_docs/%Y/%m/` |
| `PREBudgetRealignment` | `final_approved_scan` | 2871 | `br_scanned/%Y/%m/` |
| `PREBudgetRealignment` | `end_user_uploaded_document` | 2881 | `br_end_user_uploads/%Y/%m/` |
| `BudgetRealignmentSupportingDocument` | `document` | 3178 | `br_supporting_docs/%Y/%m/` |
| `BudgetRealignmentSupportingDocument` | `converted_pdf` | 3185 | `br_converted_pdfs/%Y/%m/` |

### Proposed Changes

---

#### [MODIFY] [models.py (budgets)](file:///c:/Users/John%20Romel%20Lucot/OneDrive/Desktop/Capstone%20project/capstone-projectv2/apps/budgets/models.py)

- **Remove** `from cloudinary_storage.storage import RawMediaCloudinaryStorage` (line 11)
- **Remove** every `storage=RawMediaCloudinaryStorage()` parameter from all 20 FileField declarations
- Django will automatically use the `default` storage backend defined in `settings.STORAGES`

---

#### [MODIFY] [settings.py](file:///c:/Users/John%20Romel%20Lucot/OneDrive/Desktop/Capstone%20project/capstone-projectv2/config/settings.py)

```diff
 # Modern Storage Configuration
 STORAGES = {
     "default": {
-        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
+        "BACKEND": "django.core.files.storage.FileSystemStorage",
     },
     "staticfiles": {
         "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
     },
 }

-# Cloudinary Configuration
-CLOUDINARY_STORAGE = {
-    'CLOUD_NAME': os.getenv('CLOUDINARY_CLOUD_NAME'),
-    'API_KEY': os.getenv('CLOUDINARY_API_KEY'),
-    'API_SECRET': os.getenv('CLOUDINARY_API_SECRET'),
-}

 # Media Files
 MEDIA_URL = '/media/'
 MEDIA_ROOT = BASE_DIR / 'media'
```

---

#### [MODIFY] [settings.py](file:///c:/Users/John%20Romel%20Lucot/OneDrive/Desktop/Capstone%20project/capstone-projectv2/config/settings.py) — INSTALLED_APPS

```diff
 INSTALLED_APPS = [
     ...
     # Third-party
     'django_tailwind_cli',
-    'cloudinary_storage',
-    'cloudinary',
     ...
 ]
```

---

#### [MODIFY] [requirements.txt](file:///c:/Users/John%20Romel%20Lucot/OneDrive/Desktop/Capstone%20project/capstone-projectv2/requirements.txt)

Remove:
```diff
-cloudinary==1.44.1
-django-cloudinary-storage==0.3.0
```

---

#### [MODIFY] [config/urls.py](file:///c:/Users/John%20Romel%20Lucot/OneDrive/Desktop/Capstone%20project/capstone-projectv2/config/urls.py)

Add media file serving for development and on-premise deployment:
```python
from django.conf import settings
from django.conf.urls.static import static

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

> [!IMPORTANT]
> For production on-premise, you have two options for serving media:
> 1. **Gunicorn + WhiteNoise** — WhiteNoise only handles static files, not media. You would need a reverse proxy (Nginx) in front.
> 2. **Django's `static()` helper** — Works for on-premise where traffic is low (campus network). We'll enable this with `DEBUG=False` by adding a conditional.
> 
> **Recommendation**: Use Nginx as a reverse proxy on the physical server. But for simplicity, we'll add a Django middleware approach using WhiteNoise-style serving.

---

#### Document Preview — Replace Google Docs Viewer

Since the system will be on-premise without internet, **Google Docs Viewer will not work**.

#### [MODIFY] All templates using `docs.google.com/gview` (13 references)

Replace with:
- **PDF files**: Use `<iframe src="{{ doc.document.url }}" />` — browsers can natively render PDFs
- **Images (JPG/PNG)**: Use `<img src="{{ doc.document.url }}" />`  
- **DOCX/XLSX**: Show download link only (or convert to PDF server-side using existing `xhtml2pdf`/`reportlab`)

The preview modal JavaScript will be updated to detect file type and render accordingly.

---

#### [MODIFY] [Dockerfile](file:///c:/Users/John%20Romel%20Lucot/OneDrive/Desktop/Capstone%20project/capstone-projectv2/Dockerfile)

Add a media volume mount point:
```diff
+# Create media directory
+RUN mkdir -p /app/media
+
+# Volume for persistent media storage
+VOLUME ["/app/media"]
```

---

#### [MODIFY] [start.sh](file:///c:/Users/John%20Romel%20Lucot/OneDrive/Desktop/Capstone%20project/capstone-projectv2/start.sh)

Add media directory creation:
```diff
+echo "Ensuring media directory exists..."
+mkdir -p /app/media
```

---

#### Database Migration

A new migration will be generated to remove the `storage` parameter from all FileField declarations. This is non-destructive — it only changes where Django looks for files, not the database schema.

```bash
python manage.py makemigrations budgets
python manage.py migrate
```

---

## Open Questions

> [!IMPORTANT]
> **Q1: Fresh Deployment or Data Migration?**
> Since you're deploying to a new physical server, are you starting with a fresh database? Or do you need to migrate existing data from Cloudinary? If fresh, the storage migration is straightforward. If migrating, we need a data migration script to download all Cloudinary files to local storage.

> [!IMPORTANT]
> **Q2: Nginx Reverse Proxy?**
> Will the physical server have Nginx (or Apache) as a reverse proxy in front of Gunicorn? This is recommended for:
> - Serving media files efficiently
> - SSL/TLS termination (even on campus network)
> - Request buffering and security
>
> If not, we'll configure Django to serve media files directly (acceptable for a campus network with ~50–200 users).

> [!IMPORTANT]
> **Q3: Admin Email for Notifications**
> Should notifications go to ALL staff/admin users' Gmail accounts? Or to a single designated admin email (e.g., `budget-admin@bisu.edu.ph`)? The current approach queries all `is_staff=True` users.

> [!IMPORTANT]
> **Q4: PostgreSQL on Physical Server?**
> The settings already support PostgreSQL. Will the physical server use PostgreSQL (recommended for production) or SQLite?

---

## Execution Order

The implementation will follow this order to minimize conflicts:

| Phase | Feature | Rationale |
|---|---|---|
| **Phase 1** | Local File Storage Migration | Foundational change — all other features depend on this working |
| **Phase 2** | Document Preview Fix | Must work immediately after storage migration |
| **Phase 3** | Rejection Comment Modal | UI feature, independent of storage |
| **Phase 4** | Gmail Email Notifications | Depends on rejection comment (reason is sent in email) |

---

## Verification Plan

### Automated Tests
```bash
# Run after each phase
python manage.py check --deploy       # Django deployment checklist
python manage.py makemigrations --check  # Verify no unmade migrations
python manage.py test                 # Run any existing tests
```

### Browser Testing
- Upload a file via end-user panel → verify it saves to `media/` directory
- Preview uploaded PDF/image via admin panel → verify local iframe preview works
- Reject a PR with a comment → verify modal appears, reason is saved, end user sees it
- Submit a new PR as end user → verify admin receives email notification
- Approve a PR as admin → verify end user receives email notification

### Manual Verification
- Check `media/` directory on disk for uploaded files
- Check Django admin (`/django/admin/`) for stored file paths
- Test email delivery in Gmail inbox
