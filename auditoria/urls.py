from django.urls import path

from .views import AuditoriaListView

urlpatterns = [
    path('', AuditoriaListView.as_view(), name='auditoria_lista'),
]
