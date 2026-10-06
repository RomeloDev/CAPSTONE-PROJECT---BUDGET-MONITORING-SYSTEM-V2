from django.urls import path

from . import views

urlpatterns = [
    path('api/convert-to-pdf/', views.convert_document_to_pdf, name='convert_to_pdf'),
]
