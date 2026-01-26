# Financial & Budget Management System (Capstone Project v2)

## 📌 Overview
This project is a comprehensive **Budget Management and Financial Workflow System** designed to streamline compliance and financial tracking for organizational departments. It features a robust dual-portal architecture (Admin vs. End User) ensuring strict control over budget allocations, utilization (PR/AD), and regulatory document processing.

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
    cd capstone-projectv2
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
