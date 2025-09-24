from django.urls import path
from . import views

urlpatterns = [
    path("fit/", views.fit_view, name="fit"),
]