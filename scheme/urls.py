from django.urls import path
from .views import SchemeListView, SchemeDetailView
from .views import ApplicationAPIView

urlpatterns = [
    path("api/schemes/", SchemeListView.as_view(), name="scheme-list"),
    path("api/schemes/<int:pk>/", SchemeDetailView.as_view(), name="scheme-detail"),
    path("api/application/", ApplicationAPIView.as_view(), name='application-api'),
]
