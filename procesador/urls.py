from django.urls import path
from . import views

app_name = 'procesador'

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('procesar/', views.procesar, name='procesar'),
    path('resultado/<int:sesion_id>/', views.resultado, name='resultado'),
]
