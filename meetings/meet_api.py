import json
import os
from datetime import datetime, timedelta

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from .models import (
    GoogleCredentials,
    Meeting,
    ParticipantAttendance,
    ParticipantSession,
)


# ---------------------------------------------------------
# GOOGLE CLIENT CONFIG
# ---------------------------------------------------------

def get_client_config():

    credentials_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "credentials.json"
    )

    with open(credentials_path, "r") as f:
        data = json.load(f)

    if "web" in data:
        return data["web"]

    return data["installed"]


# ---------------------------------------------------------
# CREATE GOOGLE MEET API SERVICE
# ---------------------------------------------------------

def get_meet_service(user):

    google_credentials = GoogleCredentials.objects.filter(
        user=user
    ).first()

    if not google_credentials:
        raise Exception(
            "Google credentials not found. Please authorize Google first."
        )

    client_config = get_client_config()

    credentials = Credentials(
        token=google_credentials.access_token,
        refresh_token=google_credentials.refresh_token,
        token_uri=client_config["token_uri"],
        client_id=client_config["client_id"],
        client_secret=client_config["client_secret"],
    )

    service = build(
        "meet",
        "v2",
        credentials=credentials
    )

    return service

def get_drive_service(user):

    google_credentials = GoogleCredentials.objects.filter(
        user=user
    ).first()

    if not google_credentials:
        raise Exception(
            "Google credentials not found. Please authorize Google first."
        )

    client_config = get_client_config()

    credentials = Credentials(
        token=google_credentials.access_token,
        refresh_token=google_credentials.refresh_token,
        token_uri=client_config["token_uri"],
        client_id=client_config["client_id"],
        client_secret=client_config["client_secret"],
    )

    service = build(
        "drive",
        "v3",
        credentials=credentials
    )

    return service

def find_recording_in_drive(meeting, user):

    service = get_drive_service(user)

    query = (
        "mimeType = 'video/mp4' "
        "and trashed = false "
        f"and name contains '{meeting.meeting_title}'"
    )

    response = service.files().list(
        q=query,
        spaces="drive",
        fields="files(id, name, mimeType, createdTime, webViewLink)",
        orderBy="createdTime desc",
        pageSize=100,
    ).execute()

    files = response.get(
        "files",
        []
    )

    print(
        "DRIVE RECORDINGS FOUND:",
        len(files)
    )

    for file in files:

        print(
            "DRIVE FILE:",
            file.get("name"),
            "| ID:",
            file.get("id"),
            "| CREATED:",
            file.get("createdTime")
        )

    if not files:
        return None

    recording = files[0]

    file_id = recording.get("id")

    if not file_id:
        return None

    recording_url = (
        f"https://drive.google.com/file/d/{file_id}/view"
    )

    return {
        "file_id": file_id,
        "name": recording.get("name"),
        "created_time": recording.get("createdTime"),
        "recording_url": recording_url,
    }

# ---------------------------------------------------------
# TEST FUNCTIONS
# ---------------------------------------------------------

def test_list_conferences(user):

    service = get_meet_service(user)

    response = service.conferenceRecords().list(
        pageSize=10
    ).execute()

    return response


def test_list_participants(conference_record_name, user):

    service = get_meet_service(user)

    response = service.conferenceRecords().participants().list(
        parent=conference_record_name,
        pageSize=100,
    ).execute()

    return response


def test_list_participant_sessions(participant_name, user):

    service = get_meet_service(user)

    response = (
        service.conferenceRecords()
        .participants()
        .participantSessions()
        .list(
            parent=participant_name,
            pageSize=100,
        )
        .execute()
    )

    return response


# ---------------------------------------------------------
# HELPER
# ---------------------------------------------------------

def parse_google_datetime(value):
    """
    Convert Google's UTC timestamp into a Python datetime.
    """

    if not value:
        return None

    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )

def calculate_merged_duration(sessions):
    """
    Calculate total attendance duration without double-counting
    overlapping sessions.

    Each session should have:
        joined_at
        left_at
    """

    intervals = []

    for session in sessions:

        if not session.joined_at or not session.left_at:
            continue

        intervals.append(
            (
                session.joined_at,
                session.left_at
            )
        )

    if not intervals:
        return timedelta(0)

    # Sort sessions by join time
    intervals.sort(
        key=lambda interval: interval[0]
    )

    merged_intervals = []

    current_start, current_end = intervals[0]

    for start, end in intervals[1:]:

        # Sessions overlap or touch
        if start <= current_end:

            if end > current_end:
                current_end = end

        else:

            # No overlap
            merged_intervals.append(
                (
                    current_start,
                    current_end
                )
            )

            current_start = start
            current_end = end

    # Add final interval
    merged_intervals.append(
        (
            current_start,
            current_end
        )
    )

    total_duration = timedelta(0)

    for start, end in merged_intervals:

        total_duration += end - start

    return total_duration

# ---------------------------------------------------------
# FIND CONFERENCE RECORD FOR A MEETING
# ---------------------------------------------------------

def find_conference_records_for_meeting(meeting, user):

    service = get_meet_service(user)

    print(
        "DATABASE MEETING CODE:",
        meeting.meeting_code
    )

    result = service.conferenceRecords().list(
        pageSize=100
    ).execute()

    conferences = result.get(
        "conferenceRecords",
        []
    )

    print(
        "CONFERENCES FOUND:",
        len(conferences)
    )

    matching_conferences = []

    for conference in conferences:

        conference_name = conference.get("name")
        space_name = conference.get("space")

        if not conference_name or not space_name:
            continue

        try:
            space = service.spaces().get(
                name=space_name
            ).execute()

        except Exception as e:

            print(
                "SPACE ERROR:",
                space_name,
                e
            )

            continue

        google_meeting_code = space.get(
            "meetingCode"
        )

        if google_meeting_code == meeting.meeting_code:

            start_time = conference.get("startTime")
            end_time = conference.get("endTime")

            print("\n===================================")
            print("MATCHING CONFERENCE")
            print("CONFERENCE:", conference_name)
            print("SPACE:", space_name)
            print("MEETING CODE:", google_meeting_code)
            print("START:", start_time)
            print("END:", end_time)
            print("FULL DATA:")
            print(json.dumps(conference, indent=2))
            print("===================================")

            matching_conferences.append(
                conference
            )

    print(
        "\nMATCHING CONFERENCES:",
        len(matching_conferences)
    )

    if not matching_conferences:
        return None

    # IMPORTANT:
    # Do NOT blindly return matching_conferences[0].
    #
    # For now, return the latest conference record.
    # We will verify this using the printed output.

    matching_conferences.sort(
        key=lambda conference: conference.get(
            "startTime",
            ""
        ),
        reverse=True
    )

    selected_conference = matching_conferences[0]

    print("\n===================================")
    print("SELECTED CONFERENCE")
    print(
        "CONFERENCE:",
        selected_conference.get("name")
    )
    print(
        "START:",
        selected_conference.get("startTime")
    )
    print(
        "END:",
        selected_conference.get("endTime")
    )
    print("===================================")

    return selected_conference


# ---------------------------------------------------------
# GET RECORDING FOR CONFERENCE
# ---------------------------------------------------------

def get_meeting_recording(meeting_id, user):

    meeting = Meeting.objects.get(
        id=meeting_id
    )

    # -----------------------------------------------------
    # 1. Find recording directly in Google Drive
    # -----------------------------------------------------

    recording = find_recording_in_drive(
        meeting,
        user
    )

    if not recording:

        return {
            "success": False,
            "message": (
                "No recording was found in Google Drive "
                "for this meeting."
            ),
        }

    # -----------------------------------------------------
    # 2. Save recording URL
    # -----------------------------------------------------

    meeting.recording_url = recording[
        "recording_url"
    ]

    meeting.save(
        update_fields=[
            "recording_url"
        ]
    )

    print(
        "RECORDING FOUND:",
        recording["name"]
    )

    print(
        "RECORDING URL:",
        recording["recording_url"]
    )

    return {
        "success": True,
        "message": (
            "Recording found and saved successfully."
        ),
        "recording_url": recording[
            "recording_url"
        ],
    }


# ---------------------------------------------------------
# SYNC PARTICIPANT ATTENDANCE
# ---------------------------------------------------------

def sync_meeting_attendance(meeting_id, user):

    meeting = Meeting.objects.get(
        id=meeting_id
    )

    service = get_meet_service(user)

    # -----------------------------------------------------
    # 1. Find conference record
    # -----------------------------------------------------

    conference = find_conference_records_for_meeting(
        meeting,
        user
    )

    if not conference:

        return {
            "success": False,
            "message": (
                "No Google Meet conference record "
                "was found for this meeting."
            ),
        }

    conference_record_name = conference.get(
        "name"
    )

    if not conference_record_name:
        return {
            "success": False,
            "message": (
                "Google Meet conference record name "
                "could not be determined."
            ),
        }

    # -----------------------------------------------------
    # 2. Get ACTUAL Google Meet start/end time
    # -----------------------------------------------------

    actual_start_time = parse_google_datetime(
        conference.get("startTime")
    )

    actual_end_time = parse_google_datetime(
        conference.get("endTime")
    )

    print(
        "ACTUAL MEET START:",
        actual_start_time
    )

    print(
        "ACTUAL MEET END:",
        actual_end_time
    )

    # -----------------------------------------------------
    # 3. Save conference record + actual meeting timing
    # -----------------------------------------------------

    meeting.conference_record = conference_record_name

    meeting.actual_start_time = actual_start_time

    meeting.actual_end_time = actual_end_time

    # Only calculate actual duration if Google has
    # provided both start and end times.
    if actual_start_time and actual_end_time:

        meeting.actual_duration = (
                actual_end_time - actual_start_time
        )

        print(
            "ACTUAL MEET DURATION:",
            meeting.actual_duration
        )

    else:

        print(
            "ACTUAL MEET DURATION: "
            "Not available yet. The conference may still be active."
        )

    meeting.save(
        update_fields=[
            "conference_record",
            "actual_start_time",
            "actual_end_time",
            "actual_duration",
        ]
    )

    # -----------------------------------------------------
    # 3. Get participants
    # -----------------------------------------------------

    participants_response = (
        service.conferenceRecords()
        .participants()
        .list(
            parent=conference_record_name,
            pageSize=100,
        )
        .execute()
    )

    participants = participants_response.get(
        "participants",
        []
    )

    print("PARTICIPANTS FOUND:", len(participants))
    print(
        "PARTICIPANTS RESPONSE:",
        json.dumps(participants_response, indent=2)
    )

    participant_count = 0
    session_count = 0

    # -----------------------------------------------------
    # 4. Process every participant
    # -----------------------------------------------------

    for participant_data in participants:

        print("\n========== PARTICIPANT DATA ==========")
        print(json.dumps(participant_data, indent=2))

        participant_resource = participant_data.get(
            "name"
        )

        signed_in_user = participant_data.get(
            "signedinUser",
            {}
        )

        participant_name = signed_in_user.get(
            "displayName"
        )

        participant_google_user = signed_in_user.get(
            "user"
        )

        print(
            "PARTICIPANT RESOURCE:",
            participant_resource
        )

        print(
            "GOOGLE USER:",
            participant_google_user
        )

        print(
            "DISPLAY NAME:",
            participant_name
        )

        # -------------------------------------------------
        # Email may not always be available from Meet API
        # -------------------------------------------------

        participant_email = None

        # -------------------------------------------------
        # 5. Create/update participant
        # -------------------------------------------------

        if participant_google_user:

            # For signed-in Google users, google_user is the
            # stable identity across different conferences.
            participant, created = (
                ParticipantAttendance.objects.update_or_create(
                    meeting=meeting,
                    google_user=participant_google_user,
                    defaults={
                        "participant_name": participant_name,
                        "participant_email": participant_email,
                        "participant_resource": participant_resource,
                    },
                )
            )

        else:

            # For participants without a signed-in Google identity,
            # fall back to the participant resource.
            participant, created = (
                ParticipantAttendance.objects.update_or_create(
                    meeting=meeting,
                    participant_resource=participant_resource,
                    defaults={
                        "participant_name": participant_name,
                        "participant_email": participant_email,
                    },
                )
            )

        participant_count += 1

        # -------------------------------------------------
        # 6. Get participant sessions
        # -------------------------------------------------

        sessions_response = (
            service.conferenceRecords()
            .participants()
            .participantSessions()
            .list(
                parent=participant_resource,
                pageSize=100,
            )
            .execute()
        )

        sessions = sessions_response.get(
            "participantSessions",
            []
        )

        print("\n========== PARTICIPANT SESSIONS ==========")
        print(
            json.dumps(
                sessions,
                indent=2
            )
        )

        first_joined = None
        last_left = None

        # -------------------------------------------------
        # 7. Save each session
        # -------------------------------------------------

        for session_data in sessions:

            session_resource = session_data.get(
                "name"
            )

            joined_at = parse_google_datetime(
                session_data.get("startTime")
            )

            left_at = parse_google_datetime(
                session_data.get("endTime")
            )

            if not joined_at:
                continue

            session, created = (
                ParticipantSession.objects.update_or_create(
                    participant=participant,
                    session_resource=session_resource,
                    defaults={
                        "joined_at": joined_at,
                        "left_at": left_at,
                    },
                )
            )

            # -------------------------------------------------
            # Calculate session duration
            # -------------------------------------------------

            if joined_at and left_at:
                duration = left_at - joined_at

                session.duration = duration

                session.save(
                    update_fields=["duration"]
                )

            # -------------------------------------------------
            # Find first join time
            # -------------------------------------------------

            if (
                first_joined is None
                or joined_at < first_joined
            ):

                first_joined = joined_at

            # -------------------------------------------------
            # Find last leave time
            # -------------------------------------------------

            if left_at:

                if (
                    last_left is None
                    or left_at > last_left
                ):

                    last_left = left_at

            session_count += 1

        # -------------------------------------------------
        # 8. Update participant summary
        # -------------------------------------------------

        # -------------------------------------------------
        # Calculate participant summary from ALL sessions
        # -------------------------------------------------

        all_sessions = ParticipantSession.objects.filter(
            participant=participant
        )

        participant.first_joined = (
            all_sessions
            .order_by("joined_at")
            .values_list("joined_at", flat=True)
            .first()
        )

        participant.last_left = (
            all_sessions
            .exclude(left_at=None)
            .order_by("-left_at")
            .values_list("left_at", flat=True)
            .first()
        )

        participant.total_duration = calculate_merged_duration(
            all_sessions
        )

        participant.save(
            update_fields=[
                "first_joined",
                "last_left",
                "total_duration",
            ]
        )

    # -----------------------------------------------------
    # 9. Return synchronization result
    # -----------------------------------------------------

    return {
        "success": True,
        "message": "Attendance synchronized successfully.",
        "conference_record": conference_record_name,
        "participants": participant_count,
        "sessions": session_count,
    }