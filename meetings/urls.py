from django.urls import path

from . import views


urlpatterns = [
    path(
        "",
        views.home,
        name="home",
    ),

    path(
        "authorize/",
        views.google_authorize,
        name="google-authorize",
    ),

    path(
        "oauth2callback/",
        views.google_oauth_callback,
        name="google-oauth-callback",
    ),

    path(
        "create-meeting/",
        views.create_meeting,
        name="create-meeting",
    ),

    path(
        "meetings/",
        views.meeting_list,
        name="meeting-list",
    ),

    path(
        "meetings/<int:meeting_id>/participants/",
        views.meeting_participants,
        name="meeting-attendance",
    ),

    path(
        "meetings/<int:meeting_id>/sync-attendance/",
        views.sync_attendance,
        name="sync-attendance",
    ),

    path(
        "meetings/<int:meeting_id>/test-recording/",
        views.test_meeting_recording,
        name="test-meeting-recording",
    ),
]