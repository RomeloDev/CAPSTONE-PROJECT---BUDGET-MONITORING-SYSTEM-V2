# PROJECT OVERVIEW

## System Identity

- **System Name:** BISU Balilihan Budget Monitoring System
- **Client:** Bohol Island State University — Balilihan Campus
- **Purpose:** Digitize the campus budget lifecycle — from approved budget allocation through departmental expenditure requests (PRE, PR, AD) to budget realignment — replacing paper-based tracking with a web application accessible on the campus LAN.
- **Deployment Deadline:** May 25, 2026

---

## Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Backend Framework | Django (Python) | `config.wsgi` — standard WSGI |
| Database | PostgreSQL 15 (prod) / SQLite (dev) | `dj-database-url` for switching |
| Frontend CSS | Tailwind CSS (JIT via `django_tailwind_cli`) | Utility-class only — no custom CSS files |
| Frontend JS | Vanilla JavaScript | All JS in `static/js/` — no CDN |
| WSGI Server | Gunicorn | 3 workers, 2 threads, 120s timeout |
| Reverse Proxy | Nginx | Serves `/static/` and `/media/` directly |
| Document Conversion | LibreOffice (headless mode) | Server-side DOCX/XLSX → PDF |
| Email | Gmail SMTP | App Password with 2FA |
| Static File Serving | WhiteNoise (dev/prod) + Nginx (prod) | `CompressedManifestStaticFilesStorage` |
| Time Zone | `Asia/Manila` | `USE_TZ = True` |

---

## Application Structure

The project has 4 Django apps under the `apps/` directory:

### `apps/budgets`
- **Role:** Core data layer — all financial models, budget logic, and AJAX endpoints.
- **Contains:** All models (ApprovedBudget, BudgetAllocation, DepartmentPRE, PurchaseRequest, ActivityDesign, PREBudgetRealignment, and all supporting/approved document models), signals for file cleanup and budget sync, utilities for LibreOffice conversion and budget transaction logging, and the PDF conversion AJAX endpoint.

### `apps/admin_panel`
- **Role:** Admin-facing views for budget management, request approval/rejection, user management, audit trail, and archive center.
- **Templates:** 14 HTML files + partials in `admin_panel/templates/admin_panel/`
- **Access:** Requires `is_staff=True`

### `apps/end_user_panel`
- **Role:** End-user (department) views for submitting PREs, PRs, ADs, budget realignment requests, viewing budget details, uploading signed documents, and archiving.
- **Templates:** 19 HTML files + partials in `end_user_panel/templates/end_user_panel/`
- **Access:** Requires `@login_required` (any authenticated user)

### `apps/user_accounts`
- **Role:** Custom user model (`AbstractBaseUser`), authentication, login/logout, password management, settings page.
- **Custom model:** `user_accounts.User` with role flags

---

## Deployment Target

- **Server:** Physical Windows server on campus LAN (private IP, e.g., `192.168.x.x`)
- **Network:** Campus LAN only — **no public internet access to the server from external services**
- **Reverse Proxy:** Nginx serves static/media files; proxies all other requests to Gunicorn
- **Deployment Config:** `deployment/nginx.conf` and `deployment/README.md` included in repository

---

## Key Architectural Constraints

### 1. Physical-Digital Hybrid Workflow
The system implements a hybrid workflow where:
- **Digital:** End users submit documents electronically (upload Excel/DOCX files)
- **Physical:** Admin partially approves → end user prints → physical signatures from Approving Officer → end user scans and re-uploads signed copy → admin verifies and gives final approval
- This is by design — the institution requires physical signatures on official documents

### 2. Campus LAN Deployment
- Server is accessible only on the campus LAN (private IP)
- **Google Docs Viewer cannot reach private LAN IPs** — this is expected behavior
- The 3-tier document preview system accounts for this: Google Docs Viewer is attempted but always times out, triggering the LibreOffice server-side fallback
- All JS files must be served locally from `static/js/` — no CDN dependencies

### 3. Local File Storage
- All uploads stored in `media/` directory on the server filesystem
- `STORAGES["default"]` = `django.core.files.storage.FileSystemStorage`
- Cloudinary was previously used but has been **fully removed**
- Nginx serves `/media/` files directly in production

### 4. LibreOffice Server-Side Conversion
- LibreOffice is installed on the server for headless DOCX/XLSX → PDF conversion
- Conversion is **lazy** — triggered on first preview, not at upload time
- `LIBREOFFICE_PATH` configurable via `.env` (default: `C:\Program Files\LibreOffice\program\soffice.exe`)
- `CREATE_NO_WINDOW` flag required on Windows to prevent console flash

---

## User Roles

| Role | Django Flags | Access Level |
|------|-------------|-------------|
| **End User** (Department) | `is_active=True` | `end_user_panel` — submit PRE/PR/AD, view budgets |
| **Admin** (Finance) | `is_admin=True`, `is_staff=True` | `admin_panel` — approve/reject, manage budgets/users |
| **Approving Officer** | `is_approving_officer=True` | Physical signer — signs printed documents (no special web access) |
| **Superuser** | `is_superuser=True`, `is_staff=True` | Django admin at `/django/admin/` + full admin panel |

**Key:** `create_admin()` automatically sets both `is_admin=True` and `is_staff=True`. The `User.save()` method enforces that `is_admin=True` always implies `is_staff=True`.

---

## Root URL Structure

| Prefix | App | URL Include |
|--------|-----|------------|
| `/` | `user_accounts` | Login, logout, password management |
| `/user/` | `end_user_panel` | All end-user views |
| `/admin-panel/` | `admin_panel` | All admin views |
| `/budgets/` | `budgets` | AJAX API endpoints |
| `/django/admin/` | Django built-in | Django admin interface |
