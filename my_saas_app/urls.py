"""
URL configuration for my_saas_app project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
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
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from users import views
from users.views import UserViewSet
from users.views import create_payment, home


router = DefaultRouter()
router.register(r'users', UserViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('accounts/', include('allauth.urls')),
    path('api/create-payment/', create_payment),
    # Ajoutez une route pour la page d'accueil
    path('', home, name='home'),
    path("users/", include("users.urls")),
    path('create-session/', views.create_session, name='create_session'),
    path('delete-session/', views.delete_session, name='delete_session'),
    path('save-session-state/', views.save_session_state, name='save_session_state'),
    path('load-session-state/<int:session_id>/', views.load_session_state, name='load_session_state'),

]
