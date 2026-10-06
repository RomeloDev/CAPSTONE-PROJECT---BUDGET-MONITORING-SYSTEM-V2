# BISU Balilihan - Budget Monitoring System (Capstone Project v2)

<div align="center">

![Python Version](https://img.shields.io/badge/python-3.12.3-blue.svg)
![Django Version](https://img.shields.io/badge/django-5.1.6-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

</div>

## 📌 Overview
This project is a comprehensive **Budget Management and Financial Workflow System** designed for Bohol Island State University (BISU) - Balilihan Campus.. It features a robust dual-portal architecture (Admin vs. End User) ensuring strict control over budget allocations, utilization (PR/AD), and regulatory document processing.

## About the Project

The **BISU Balilihan Budget Monitoring System** is a capstone project developed to streamline and modernize the budget management processes at Bohol Island State University - Balilihan Campus. The system provides real-time monitoring, tracking, and reporting of budget allocations, expenditures, and financial requests across different departments.

### Problem Statement

Traditional budget management at BISU Balilihan involved:
- Manual tracking of budget allocations and expenditures
- Paper-based document processing
- Difficulty in real-time budget monitoring
- Lack of centralized data management
- Time-consuming approval workflows

### Solution

This system provides:
- ✅ Centralized budget tracking and monitoring
- ✅ Digital document management
- ✅ Automated workflow approvals
- ✅ Real-time budget utilization reports
- ✅ Multi-level user access control
- ✅ Comprehensive audit trails
- ✅ Excel/PDF report generation

---

## 🚀 Key Features

### 🏛️ Budget Management
*   **Allocation System:** Centralized distribution of funds to departments.
*   **Real-time Monitoring:** Live tracking of Allocated, Utilized, and Remaining balances.
*   **Realignment Workflow:** Structured approval process for transferring funds between budget lines (Source → Target).

### 📄 Document Workflow (PRE/PR/AD)
*   **PRE (Program of Receipts and Expenditures):** Digital creation, validation, and approval workflow.
*   **Purchase Requests (PR) & Activity Designs (AD):** Automated fund deduction and status tracking (Draft → Pending → Approved).
*   **Digital Signatures:** Secure upload and verification of signed documents.

### 🛡️ Audit & Archive
*   **Comprehensive Audit Trail:** Logs every financial transaction and sensitive action for accountability.
*   **Cascade Archiving:** Ability to archive entire Fiscal Years or specific Allocations, automatically cascading to all related documents.
*   **Restore Capability:** Granular restore functionality for archived records.

### 📊 Reporting
*   **PDF Generation:** Automated export of:
    *   Budget Summary Reports
    *   Quarterly Utilization Reports
    *   Transaction History Logs

## 💻 Tech Stack
*   **Backend:** Python 3.x, Django 5.x
*   **Frontend:** HTML5, Tailwind CSS, JavaScript
*   **Database:** SQLite (default) / PostgreSQL compatible
*   **Storage:** Cloudinary (media hosting)
*   **Authentication:** Django Custom User Model

## 🛠️ Setup Instructions

1.  **Clone the Repo**
    ```bash
    git clone <repository_url>
    cd CAPSTONE-PROJECT---BUDGET-MONITORING-SYSTEM-V2
    ```

2.  **Create Virtual Env**
    ```bash
    python -m venv venv
    venv\Scripts\activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment**
    Create a `.env` file in the root directory:
    ```env
    SECRET_KEY=your_secret_key
    DEBUG=True
    CLOUDINARY_URL=cloudinary://...
    ```

5.  **Run Migrations**
    ```bash
    python manage.py makemigrations
    python manage.py migrate
    ```

6.  **Create Admin**
    ```bash
    python manage.py createsuperuser
    ```

7.  **Run Server**
    ```bash
    python manage.py runserver
    ```

## 📂 Project Structure
*   `apps/` - Core applications (`budgets`, `admin_panel`, `end_user_panel`)
*   `config/` - Project settings
*   `static/` - Static assets
*   `templates/` - HTML templates

## 📄 License
This project is licensed under the MIT License - see the `LICENSE` file for details.


## Screenshots

### Admin panel

![Admin panel: 095728](https://github.com/RomeloDev/CAPSTONE-PROJECT---BUDGET-MONITORING-SYSTEM-V2/blob/main/static/screenshots/Admin_panel/Screenshot%202026-01-23%20095728.png)

![Admin panel: 095903](static/screenshots/Admin_panel/Screenshot 2026-01-23 095903.png)

![Admin panel: 095912](static/screenshots/Admin_panel/Screenshot 2026-01-23 095912.png)

![Admin panel: 095927](static/screenshots/Admin_panel/Screenshot 2026-01-23 095927.png)

![Admin panel: 095932](static/screenshots/Admin_panel/Screenshot 2026-01-23 095932.png)

![Admin panel: 095939](static/screenshots/Admin_panel/Screenshot 2026-01-23 095939.png)

![Admin panel: 100015](static/screenshots/Admin_panel/Screenshot 2026-01-23 100015.png)

![Admin panel: 100103](static/screenshots/Admin_panel/Screenshot 2026-01-23 100103.png)

![Admin panel: 100110](static/screenshots/Admin_panel/Screenshot 2026-01-23 100110.png)

![Admin panel: 100116](static/screenshots/Admin_panel/Screenshot 2026-01-23 100116.png)

![Admin panel: at 09:59:55 Admin Department's Purchase Request](static/screenshots/Admin_panel/Screenshot 2026-01-23 at 09-59-55 Admin Department's Purchase Request.png)

### End user panel

![End user panel: 100126](static/screenshots/End_user_panel/Screenshot 2026-01-23 100126.png)

![End user panel: 100140](static/screenshots/End_user_panel/Screenshot 2026-01-23 100140.png)

![End user panel: 100146](static/screenshots/End_user_panel/Screenshot 2026-01-23 100146.png)

![End user panel: 100255](static/screenshots/End_user_panel/Screenshot 2026-01-23 100255.png)

![End user panel: 100350](static/screenshots/End_user_panel/Screenshot 2026-01-23 100350.png)

![End user panel: 100409](static/screenshots/End_user_panel/Screenshot 2026-01-23 100409.png)

![End user panel: 100450](static/screenshots/End_user_panel/Screenshot 2026-01-23 100450.png)

![End user panel: 100458](static/screenshots/End_user_panel/Screenshot 2026-01-23 100458.png)

![End user panel: 100718](static/screenshots/End_user_panel/Screenshot 2026-01-23 100718.png)

