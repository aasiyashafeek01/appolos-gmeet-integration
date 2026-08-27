import uuid
import secrets

from django.contrib.auth import login
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_datetime
from django.utils import timezone

from django.http import (
    HttpResponse,
    JsonResponse,
)

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from .calendar_api import get_calendar_service
from .models import (
    Meeting,
    GoogleCredentials,
    MeetingParticipant,
    Conference,
)
from .google_api import get_google_flow
from .meet_api import (
    get_meeting_recording,
    sync_meeting_attendance,
    set_auto_recording,
    get_meeting_space,
)


# =========================================================
# HOME
# =========================================================

def home(request):

    return render(
        request,
        "meetings/home.html"
    )


# =========================================================
# GOOGLE AUTHORIZATION
# =========================================================

def google_authorize(request):

    code_verifier = secrets.token_urlsafe(64)

    flow = get_google_flow(
        code_verifier=code_verifier
    )

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    request.session["oauth_state"] = state
    request.session["code_verifier"] = code_verifier
    request.session["oauth_next"] = request.GET.get(
        "next",
        "home"
    )

    request.session.save()

    return redirect(authorization_url)


# =========================================================
# GOOGLE OAUTH CALLBACK
# =========================================================

def google_oauth_callback(request):

    state = request.GET.get("state")
    code = request.GET.get("code")

    saved_state = request.session.get(
        "oauth_state"
    )

    code_verifier = request.session.get(
        "code_verifier"
    )

    next_page = request.session.get(
        "oauth_next",
        "home"
    )

    if next_page == "create":
        next_page = "create-meeting"

    # ---------------------------------------------
    # Validate OAuth response
    # ---------------------------------------------

    if not state:

        return HttpResponse(
            "Google did not return OAuth state.",
            status=400
        )

    if not code:

        return HttpResponse(
            "Google did not return an authorization code.",
            status=400
        )

    if not saved_state:

        return HttpResponse(
            "OAuth state is missing from Django session. "
            "Start the login process again.",
            status=400
        )

    if not code_verifier:

        return HttpResponse(
            "PKCE code verifier is missing from Django session. "
            "Start the login process again.",
            status=400
        )

    if state != saved_state:

        return HttpResponse(
            "OAuth state mismatch. Start the login process again.",
            status=400
        )

    # ---------------------------------------------
    # Exchange authorization code
    # ---------------------------------------------

    flow = get_google_flow(
        code_verifier=code_verifier
    )

    flow.state = saved_state

    flow.fetch_token(
        code=code,
        code_verifier=code_verifier,
    )

    credentials = flow.credentials

    # ---------------------------------------------
    # Identify Google account
    # ---------------------------------------------

    if not credentials.id_token:

        return HttpResponse(
            "Google did not return an identity token.",
            status=400
        )

    try:

        google_user_info = id_token.verify_oauth2_token(
            credentials.id_token,
            google_requests.Request()
        )

    except ValueError:

        return HttpResponse(
            "Unable to verify Google account identity.",
            status=400
        )

    google_email = google_user_info.get(
        "email"
    )

    google_name = google_user_info.get(
        "name",
        google_email
    )

    if not google_email:

        return HttpResponse(
            "Google account email was not available.",
            status=400
        )

    # ---------------------------------------------
    # Find or create Django user
    # ---------------------------------------------

    user, created = User.objects.get_or_create(
        username=google_email,
        defaults={
            "email": google_email,
            "first_name": google_name,
        },
    )

    if not user.email:
        user.email = google_email

    if not user.first_name and google_name:
        user.first_name = google_name

    user.save()

    # ---------------------------------------------
    # Log user into Django
    # ---------------------------------------------

    login(
        request,
        user
    )

    # ---------------------------------------------
    # Save Google credentials
    # ---------------------------------------------

    GoogleCredentials.objects.update_or_create(
        user=user,
        defaults={
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_expiry": credentials.expiry,
        },
    )

    # ---------------------------------------------
    # Clean OAuth session
    # ---------------------------------------------

    request.session.pop(
        "oauth_state",
        None
    )

    request.session.pop(
        "code_verifier",
        None
    )

    request.session.pop(
        "oauth_next",
        None
    )

    return redirect(next_page)


# =========================================================
# CREATE MEETING
# =========================================================

def create_meeting(request):

    # ---------------------------------------------
    # Make sure user is logged in
    # ---------------------------------------------

    if not request.user.is_authenticated:

        return redirect(
            "/authorize/?next=create-meeting"
        )

    # ---------------------------------------------
    # Make sure this user has Google credentials
    # ---------------------------------------------

    if not GoogleCredentials.objects.filter(
        user=request.user
    ).exists():

        return redirect(
            "/authorize/?next=create-meeting"
        )

    if request.method == "POST":

        meeting_title = request.POST.get(
            "meeting_title"
        )

        start_time = request.POST.get(
            "start_time"
        )

        end_time = request.POST.get(
            "end_time"
        )

        participant_emails = request.POST.get(
            "participant_emails",
            ""
        )

        participant_emails = [
            email.strip()
            for email in participant_emails.split(",")
            if email.strip()
        ]

        auto_record = (
                request.POST.get("auto_record") == "on"
        )

        # -----------------------------------------
        # Validate required fields
        # -----------------------------------------

        if (
            not meeting_title
            or not start_time
            or not end_time
        ):

            return HttpResponse(
                "Meeting title, start time and end time are required.",
                status=400
            )

        # -----------------------------------------
        # Convert form datetime values
        # -----------------------------------------

        start_datetime = parse_datetime(
            start_time
        )

        end_datetime = parse_datetime(
            end_time
        )

        if not start_datetime or not end_datetime:

            return HttpResponse(
                "Invalid date/time format.",
                status=400
            )

        # -----------------------------------------
        # Make datetimes timezone-aware
        # -----------------------------------------

        india_timezone = timezone.get_fixed_timezone(
            330
        )

        start_datetime = start_datetime.replace(
            tzinfo=india_timezone
        )

        end_datetime = end_datetime.replace(
            tzinfo=india_timezone
        )

        if end_datetime <= start_datetime:

            return HttpResponse(
                "End time must be after start time.",
                status=400
            )

        # -----------------------------------------
        # Get THIS USER'S Google Calendar service
        # -----------------------------------------

        service = get_calendar_service(
            request.user
        )

        event = {

            "summary": meeting_title,

            "start": {
                "dateTime": start_datetime.isoformat(),
                "timeZone": "Asia/Kolkata",
            },

            "end": {
                "dateTime": end_datetime.isoformat(),
                "timeZone": "Asia/Kolkata",
            },

            "conferenceData": {

                "createRequest": {

                    "requestId": str(
                        uuid.uuid4()
                    ),

                    "conferenceSolutionKey": {
                        "type": "hangoutsMeet"
                    },
                }
            },
        }

        # -----------------------------------------
        # Add participants if provided
        # -----------------------------------------

        if participant_emails:

            event["attendees"] = [
                {
                    "email": email
                }
                for email in participant_emails
            ]

        # -----------------------------------------
        # Create Calendar event + Meet
        # -----------------------------------------

        created_event = service.events().insert(
            calendarId="primary",
            body=event,
            conferenceDataVersion=1,
            sendUpdates="all",
        ).execute()

        # -----------------------------------------
        # Extract Meet link
        # -----------------------------------------

        conference_data = created_event.get(
            "conferenceData",
            {}
        )

        meet_link = None

        for entry_point in conference_data.get(
            "entryPoints",
            []
        ):

            if entry_point.get(
                "entryPointType"
            ) == "video":

                meet_link = entry_point.get(
                    "uri"
                )

                break

        if not meet_link:

            return HttpResponse(
                "Meeting created, but Google Meet link "
                "was not generated yet."
            )

        # -----------------------------------------
        # Extract meeting code
        # -----------------------------------------

        meeting_code = (
            meet_link.rstrip("/")
            .split("/")[-1]
        )

        # -----------------------------------------
        # Get Google Meet space resource
        # -----------------------------------------

        space_result = get_meeting_space(
            meeting_code,
            request.user
        )

        if not space_result["success"]:
            return HttpResponse(
                "Meeting was created, but the Google Meet "
                "space could not be retrieved: "
                + space_result.get(
                    "message",
                    "Unknown error."
                ),
                status=500
            )

        space_name = space_result["space_name"]

        # -----------------------------------------
        # Save Meeting
        # -----------------------------------------

        meeting = Meeting.objects.create(
            user=request.user,
            meeting_title=meeting_title,
            gmeet_link=meet_link,
            meeting_code=meeting_code,
            space_name=space_name,
            start_time=start_datetime,
            end_time=end_datetime,
            auto_record=auto_record,
        )

        # -----------------------------------------
        # Configure Google Meet auto recording
        # -----------------------------------------

        if auto_record:

            recording_result = set_auto_recording(
                meeting,
                request.user,
                enabled=True
            )

            if not recording_result["success"]:
                # Remove the local meeting record because
                # the requested recording configuration failed.
                meeting.delete()

                return HttpResponse(
                    "Meeting was created, but automatic recording "
                    "could not be enabled: "
                    + recording_result.get(
                        "message",
                        "Unknown error."
                    ),
                    status=500
                )

        # -----------------------------------------
        # Save invited participants
        # -----------------------------------------

        for email in participant_emails:

            MeetingParticipant.objects.create(
                meeting=meeting,
                email=email
            )

        return render(
            request,
            "meetings/meeting_success.html",
            {
                "meeting": meeting
            }
        )

    return render(
        request,
        "meetings/create_meeting.html"
    )


# =========================================================
# MEETING LIST
# =========================================================

def meeting_list(request):

    # ---------------------------------------------
    # Make sure user is logged in
    # ---------------------------------------------

    if not request.user.is_authenticated:

        return redirect(
            "/authorize/?next=meeting-list"
        )

    # ---------------------------------------------
    # Make sure this user has Google credentials
    # ---------------------------------------------

    if not GoogleCredentials.objects.filter(
        user=request.user
    ).exists():

        return redirect(
            "/authorize/?next=meeting-list"
        )

    # ---------------------------------------------
    # ONLY show this user's meetings
    # ---------------------------------------------

    meetings = (
        Meeting.objects
        .filter(
            user=request.user
        )
        .prefetch_related(
            "conferences__recordings"
        )
        .order_by(
            "-start_time"
        )
    )

    return render(
        request,
        "meetings/meeting_list.html",
        {
            "meetings": meetings
        }
    )

# =========================================================
# MEETING PARTICIPANTS
# =========================================================

def meeting_participants(
    request,
    meeting_id
):

    # ---------------------------------------------
    # Make sure user is logged in
    # ---------------------------------------------

    if not request.user.is_authenticated:

        return redirect(
            "/authorize/?next=meeting-list"
        )

    # ---------------------------------------------
    # Make sure THIS user has Google credentials
    # ---------------------------------------------

    if not GoogleCredentials.objects.filter(
        user=request.user
    ).exists():

        return redirect(
            "/authorize/?next=meeting-list"
        )

    # ---------------------------------------------
    # Only retrieve THIS user's meeting
    # ---------------------------------------------

    try:

        meeting = (
            Meeting.objects
            .prefetch_related(
                "conferences__participants__sessions"
            )
            .get(
                id=meeting_id,
                user=request.user
            )
        )

    except Meeting.DoesNotExist:

        return HttpResponse(
            "Meeting not found.",
            status=404
        )

    # ---------------------------------------------
    # Invited participants
    # ---------------------------------------------

    invited_participants = (
        meeting.invited_participants.all()
    )

    # ---------------------------------------------
    # Conferences belonging to this meeting
    # ---------------------------------------------

    conferences = (
        meeting.conferences
        .prefetch_related(
            "participants__sessions"
        )
        .order_by(
            "start_time"
        )
    )

    return render(
        request,
        "meetings/meeting_participants.html",
        {
            "meeting": meeting,
            "invited_participants": invited_participants,
            "conferences": conferences,
        }
    )


# =========================================================
# SYNC ATTENDANCE
# =========================================================

def sync_attendance(
    request,
    meeting_id
):

    # ---------------------------------------------
    # Make sure user is logged in
    # ---------------------------------------------

    if not request.user.is_authenticated:

        return redirect(
            "/authorize/?next=meeting-list"
        )

    # ---------------------------------------------
    # Only allow access to THIS user's meeting
    # ---------------------------------------------

    try:

        meeting = Meeting.objects.get(
            id=meeting_id,
            user=request.user
        )

    except Meeting.DoesNotExist:

        return HttpResponse(
            "Meeting not found.",
            status=404
        )

    # ---------------------------------------------
    # Synchronize attendance
    # ---------------------------------------------

    result = sync_meeting_attendance(
        meeting.id,
        request.user
    )

    if not result["success"]:

        return HttpResponse(
            result["message"],
            status=404
        )

    # ---------------------------------------------
    # Return to participant page
    # ---------------------------------------------

    return redirect(
        "meeting-attendance",
        meeting_id=meeting.id
    )


# =========================================================
# TEST MEETING RECORDINGS
# =========================================================

def test_meeting_recording(
    request,
    meeting_id
):

    # ---------------------------------------------
    # Make sure user is logged in
    # ---------------------------------------------

    if not request.user.is_authenticated:

        return redirect(
            "/authorize/?next=meeting-list"
        )

    # ---------------------------------------------
    # Only allow access to THIS user's meeting
    # ---------------------------------------------

    try:

        meeting = Meeting.objects.get(
            id=meeting_id,
            user=request.user
        )

    except Meeting.DoesNotExist:

        return HttpResponse(
            "Meeting not found.",
            status=404
        )

    # ---------------------------------------------
    # Get recordings
    # ---------------------------------------------

    result = get_meeting_recording(
        meeting.id,
        request.user
    )

    if not result["success"]:

        return HttpResponse(
            f"""
            <h2>Recording Test</h2>

            <p>{result["message"]}</p>
            """,
            status=404
        )

    # ---------------------------------------------
    # Display all recordings
    # ---------------------------------------------

    recordings_html = ""

    for recording in result.get(
        "recordings",
        []
    ):

        recording_url = recording.get(
            "recording_url"
        )

        if recording_url:

            recordings_html += f"""
                <li>
                    <strong>
                        Conference:
                    </strong>
                    {recording["conference_id"]}

                    <br>

                    <strong>
                        Recording:
                    </strong>

                    <a
                        href="{recording_url}"
                        target="_blank"
                    >
                        Open Recording
                    </a>

                    <br>

                    <strong>
                        Start:
                    </strong>
                    {recording["start_time"]}

                    <br>

                    <strong>
                        End:
                    </strong>
                    {recording["end_time"]}
                </li>

                <br>
            """

        else:

            recordings_html += f"""
                <li>
                    Conference:
                    {recording["conference_id"]}

                    <br>

                    Recording URL is not available.
                </li>

                <br>
            """

    return HttpResponse(
        f"""
        <h2>Recordings Found</h2>

        <p>
            {result["message"]}
        </p>

        <p>
            Total recordings:
            {len(result.get("recordings", []))}
        </p>

        <ul>
            {recordings_html}
        </ul>
        """
    )