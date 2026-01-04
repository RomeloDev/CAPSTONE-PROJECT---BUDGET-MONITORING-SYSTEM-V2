from io import BytesIO
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa

def render_to_pdf(template_src, context_dict={}):
    """
    Render a Django template into a PDF response.
    """
    template = get_template(template_src)
    html  = template.render(context_dict)
    result = BytesIO()
    
import os
from django.conf import settings

def link_callback(uri, rel):
    """
    Convert HTML URIs to absolute system paths so xhtml2pdf can access those resources
    """
    sUrl = settings.STATIC_URL        # Typically /static/
    sRoot = settings.STATIC_ROOT      # Typically /home/user/var/www/static/
    mUrl = settings.MEDIA_URL         # Typically /media/
    mRoot = settings.MEDIA_ROOT       # Typically /home/user/var/www/media/

    if uri.startswith(mUrl):
        path = os.path.join(mRoot, uri.replace(mUrl, ""))
    elif uri.startswith(sUrl):
        path = os.path.join(sRoot, uri.replace(sUrl, ""))
        # Fallback to STATICFILES_DIRS if not found in STATIC_ROOT (for dev)
        if not os.path.isfile(path) and settings.STATICFILES_DIRS:
             path = os.path.join(settings.STATICFILES_DIRS[0], uri.replace(sUrl, ""))
    else:
        return uri

    # Make sure that file exists
    if not os.path.isfile(path):
            raise Exception(
                'media URI must start with %s or %s' % (sUrl, mUrl)
            )
    return path

def render_to_pdf(template_src, context_dict={}):
    """
    Render a Django template into a PDF response.
    """
    template = get_template(template_src)
    html  = template.render(context_dict)
    result = BytesIO()
    
    # Generate PDF with link_callback
    pdf = pisa.pisaDocument(
        BytesIO(html.encode("UTF-8")), 
        result,
        link_callback=link_callback
    )
    
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    return None
