import os
import shutil
import subprocess
import tempfile
import logging
import traceback
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from decimal import Decimal
from .models import BudgetTransaction

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Document Preview — LibreOffice PDF Conversion Utilities
# ---------------------------------------------------------------------------

IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
PDF_CONVERTIBLE = {'docx', 'doc', 'xlsx', 'xls', 'pptx', 'ppt', 'odt', 'ods'}


def get_file_extension(filename):
    """Return lowercase file extension without dot."""
    return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''


def needs_conversion(filename):
    """True if the file type requires LibreOffice conversion for preview."""
    return get_file_extension(filename) in PDF_CONVERTIBLE


def convert_to_pdf_with_libreoffice(input_path):
    """
    Convert a file to PDF using LibreOffice headless mode.

    Returns the PDF file contents as bytes on success, or None on failure.
    Uses a temporary directory for output to avoid naming collisions.
    Never raises — logs errors and returns None.
    """
    try:
        # Resolve soffice: PATH lookup first, then settings fallback
        soffice = shutil.which('soffice') or getattr(
            settings, 'LIBREOFFICE_PATH',
            r'C:\Program Files\LibreOffice\program\soffice.exe'
        )

        input_path = str(input_path)

        with tempfile.TemporaryDirectory() as tmp_dir:
            result = subprocess.run(
                [soffice, '--headless', '--convert-to', 'pdf',
                 '--outdir', tmp_dir, input_path],
                timeout=60,
                capture_output=True,
                text=True,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                ),
            )

            if result.returncode != 0:
                logger.error(
                    "[LibreOffice] Conversion failed for %s: %s",
                    input_path, result.stderr
                )
                return None

            pdf_filename = Path(input_path).stem + '.pdf'
            pdf_path = os.path.join(tmp_dir, pdf_filename)

            if not os.path.exists(pdf_path):
                logger.error(
                    "[LibreOffice] PDF not found after conversion: %s",
                    pdf_path
                )
                return None

            logger.info(
                "[LibreOffice] Converted: %s -> %s", input_path, pdf_path
            )
            with open(pdf_path, 'rb') as f:
                return f.read()

    except subprocess.TimeoutExpired:
        logger.error("[LibreOffice] Timed out for: %s", input_path)
    except Exception:
        logger.error(
            "[LibreOffice] Unexpected error:\n%s", traceback.format_exc()
        )
    return None


def attach_converted_pdf(instance, source_field_name, pdf_field_name):
    """
    Convert a document field to PDF and save it on the model instance.

    Parameters:
        instance: model instance (already saved)
        source_field_name: name of the FileField with the original file
        pdf_field_name: name of the FileField to store the converted PDF

    Fails silently — logs errors but never raises.
    """
    source_field = getattr(instance, source_field_name, None)
    if not source_field or not source_field.name:
        return

    if not needs_conversion(source_field.name):
        return

    pdf_bytes = convert_to_pdf_with_libreoffice(source_field.path)
    if pdf_bytes is None:
        return

    pdf_filename = Path(source_field.name).stem + '.pdf'
    getattr(instance, pdf_field_name).save(
        pdf_filename, ContentFile(pdf_bytes), save=True
    )


# ---------------------------------------------------------------------------
# Budget Transaction Logging
# ---------------------------------------------------------------------------

def log_budget_transaction(allocation, amount, transaction_type, user, remarks='', update_allocation=True):
    """
    Robust utility to handle financial audit logging with Snapshot Logic.
    
    Args:
        allocation: The BudgetAllocation instance.
        amount (Decimal): The amount changing (positive for credit, negative for debit).
        transaction_type (str): e.g., "Realignment", "Expense", "Supplement".
        user: The user making the change.
        remarks (str): Optional text.
        update_allocation (bool): If True, updates the allocation.allocated_amount and saves it.
                                  Set to False if you want to handle the parent update manually
                                  or if this transaction affects a different field (like only remaining_balance).
    """
    with transaction.atomic():
        amount_decimal = Decimal(str(amount))
        new_balance = allocation.allocated_amount 
        previous_balance = allocation.allocated_amount - amount_decimal
        
        BudgetTransaction.objects.create(
            allocation=allocation,
            transaction_type=transaction_type,
            amount=amount_decimal,
            previous_balance=previous_balance,
            new_balance=new_balance,
            remarks=remarks,
            created_by=user
        )
        
        if update_allocation:
            allocation.allocated_amount = new_balance
            
            # Recalculate remaining balance if the allocation changes
            # (Assuming remaining = allocated - used)
            # We call the model's update method if it exists, or do it manually
            if hasattr(allocation, 'update_remaining_balance'):
                allocation.update_remaining_balance()
            else:
                # Fallback manual calculation
                total_used = allocation.get_total_used() if hasattr(allocation, 'get_total_used') else Decimal('0.00')
                allocation.remaining_balance = allocation.allocated_amount - total_used
                allocation.save() # Saved inside the atomic block
