"""
URL configuration for FlowMigao project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.urls import path, include
from django.shortcuts import render

def home(request):
    return render(request, 'home.html')

def saude(request):
    # Usado pelo healthcheck do Railway: o deploy só entra no ar se o app responder e o banco conectar
    try:
        connection.ensure_connection()
    except DatabaseError:
        return JsonResponse({'status': 'erro', 'banco': 'indisponível'}, status=503)
    return JsonResponse({'status': 'ok'})

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('saude/', saude, name='saude'),
    path('clientes/', include('clientes.urls')),
    path('veiculos/', include('veiculos.urls')),
    path('manutencoes/', include('manutencoes.urls')),
]