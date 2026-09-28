from django.urls import path

from .views import AuditoriaListView, TentativaLoginListView

urlpatterns = [
    path('', AuditoriaListView.as_view(), name='auditoria_lista'),
    path('logins/', TentativaLoginListView.as_view(), name='auditoria_logins'),
]
