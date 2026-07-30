"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
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
from django.conf import settings
from django.views.generic import RedirectView
from django.views.static import serve
from django.urls import re_path
from spese.views import api_chat,api_chat_send
from spese.views import CreateStoreTemplateView, InternalTaskEventAPIView,login_view,logout_view
from core import settings


urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path('admin/', admin.site.urls),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path("",RedirectView.as_view(pattern_name="report_spese", permanent=False)),
    path('scontrini/', include('spese.urls')),
    path('api/internal/events/', InternalTaskEventAPIView.as_view(), name='internal_events'),
    path("api/supermercati/create/",CreateStoreTemplateView.as_view(),
    name="api_create_supermercato"),
    path('api/chat/',api_chat,name='api_chat'),
    path("api/chat/send/",api_chat_send,name="api_chat_send"),

]
if settings.SERVE_MEDIA:
    urlpatterns += [
        re_path(
            r"^media/(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]