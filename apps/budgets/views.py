import json
import uuid

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import (
    DepartmentPRE,
    PurchaseRequest,
    ActivityDesign,
    DepartmentPRESupportingDocument,
    PurchaseRequestSupportingDocument,
    ActivityDesignSupportingDocument,
    BudgetRealignmentSupportingDocument,
    PurchaseRequestApprovedDocument,
    ActivityDesignApprovedDocument,
    SupportingDocument,
)
from .utils import attach_converted_pdf

# ---------------------------------------------------------------------------
# Document type whitelist
# Maps the document_type string sent by the frontend to:
#   (Model class, source file field name, converted PDF field name, pk_is_uuid)
# ---------------------------------------------------------------------------
DOCUMENT_TYPE_MAP = {
    'pre_supporting_doc': (DepartmentPRESupportingDocument,  'document', 'converted_pdf',        False),
    'pr_supporting_doc':  (PurchaseRequestSupportingDocument, 'document', 'converted_pdf',        False),
    'ad_supporting_doc':  (ActivityDesignSupportingDocument,  'document', 'converted_pdf',        False),
    'br_supporting_doc':  (BudgetRealignmentSupportingDocument,'document','converted_pdf',        False),
    'pr_approved_doc':    (PurchaseRequestApprovedDocument,   'document', 'converted_pdf',        False),
    'ad_approved_doc':    (ActivityDesignApprovedDocument,    'document', 'converted_pdf',        False),
    'ab_supporting_doc':  (SupportingDocument,                'document', 'converted_pdf',        False),
    'pre_main':           (DepartmentPRE,   'uploaded_excel_file', 'uploaded_excel_pdf',          True),
    'pr_main':            (PurchaseRequest, 'uploaded_document',   'uploaded_document_pdf',       True),
    'ad_main':            (ActivityDesign,  'uploaded_document',   'uploaded_document_pdf',       True),
}


@login_required
@require_POST
def convert_document_to_pdf(request):
    """
    AJAX endpoint — lazy LibreOffice PDF conversion (Tier 2 of preview system).

    Request body (JSON):
        document_id:   str  — UUID string for parent models, integer string for
                              supporting/approved document models
        document_type: str  — one of the keys in DOCUMENT_TYPE_MAP

    Response (JSON):
        { "success": true,  "pdf_url": "/media/..." }
        { "success": false, "error": "..." }
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Invalid JSON.'}, status=400)

    document_type = body.get('document_type', '').strip()
    document_id   = body.get('document_id', '')

    # Validate document_type against whitelist
    if document_type not in DOCUMENT_TYPE_MAP:
        return JsonResponse(
            {'success': False, 'error': f'Unknown document type: {document_type}'},
            status=400,
        )

    model_class, source_field, pdf_field, pk_is_uuid = DOCUMENT_TYPE_MAP[document_type]

    # Parse the primary key — UUID for parent models, int for supporting/approved docs
    try:
        if pk_is_uuid:
            pk = uuid.UUID(str(document_id))
        else:
            pk = int(document_id)
    except (ValueError, AttributeError):
        return JsonResponse({'success': False, 'error': 'Invalid document ID.'}, status=400)

    # Fetch the instance
    try:
        instance = model_class.objects.get(pk=pk)
    except model_class.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Document not found.'}, status=404)

    # Fast path: converted PDF already exists — return immediately, no conversion
    existing_pdf = getattr(instance, pdf_field, None)
    if existing_pdf and existing_pdf.name:
        return JsonResponse({'success': True, 'pdf_url': existing_pdf.url})

    # Slow path: run LibreOffice conversion
    attach_converted_pdf(instance, source_field, pdf_field)

    # Re-read the field after save
    instance.refresh_from_db(fields=[pdf_field])
    new_pdf = getattr(instance, pdf_field, None)

    if new_pdf and new_pdf.name:
        return JsonResponse({'success': True, 'pdf_url': new_pdf.url})

    return JsonResponse({'success': False, 'error': 'Conversion failed.'})
