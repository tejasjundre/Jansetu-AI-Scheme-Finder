from django.urls import path

from . import views


urlpatterns = [
    path("healthz/", views.healthz, name="healthz"),
    path("", views.home, name="home"),
    path("wizard/", views.wizard, name="wizard"),
    path("chat/", views.chat, name="chat"),
    path("schemes/", views.schemes, name="schemes"),
    path("scheme/<slug:slug>/", views.scheme_detail, name="scheme_detail"),
    path("support/", views.support, name="support"),
    path("privacy/", views.privacy, name="privacy"),
    path("ops/", views.ops_dashboard, name="ops_dashboard"),
    path("api/chat/", views.chat_api, name="chat_api"),
    path("api/help-center/", views.help_center_api, name="help_center_api"),
    path("api/speech-to-text/", views.speech_to_text_api, name="speech_to_text_api"),
    path("api/text-to-speech/", views.text_to_speech_api, name="text_to_speech_api"),
]
