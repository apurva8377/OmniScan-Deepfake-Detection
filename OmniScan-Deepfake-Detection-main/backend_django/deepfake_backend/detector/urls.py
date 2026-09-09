from django.urls import path
from . import views

urlpatterns = [
    # This creates the endpoint: /api/analyze/
    path('analyze/', views.analyze_video, name='analyze_video'),
]