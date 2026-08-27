import json
import os
from datetime import datetime, timedelta

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from .models import (
    GoogleCredentials,
    Meeting,
    Conference,
    ParticipantAttendance,
    ParticipantSession,
    ConferenceRecording,
)


# =========================================================
# GOOGLE CLIENT CONFIG
# =========================================================

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


# =========================================================
# GOOGLE CREDENTIALS
# =========================================================

def get_google_credentials(user):

    google_credentials = (
        GoogleCredentials.objects
        .filter(user=user)
        .first()
    )

    if not google_credentials:
        raise Exception(
            "Google credentials not found. "
            "Please authorize Google first."
        )

    client_config = get_client_config()

    credentials = Credentials(
        token=google_credentials.access_token,
        refresh_token=google_credentials.refresh_token,
        token_uri=client_config["token_uri"],
        client_id=client_config["client_id"],
        client_secret=client_config["client_secret"],
    )

    return credentials


# =========================================================
# GOOGLE MEET SERVICE
# =========================================================

def get_meet_service(user):

    credentials = get_google_credentials(user)

    service = build(
        "meet",
        "v2",
        credentials=credentials
    )

    return service

# =========================================================
# GET GOOGLE MEET SPACE
# =========================================================

def get_meeting_space(
    meeting_code,
    user
):
    """
    Retrieve the Google Meet space resource using
    the meeting code.

    Example:

        meeting_code:
            abc-defg-hij

        returned space:
            spaces/XXXXXXXXXXXX
    """

    if not meeting_code:

        return {
            "success": False,
            "space_name": None,
            "message": "Meeting code is not available."
        }

    service = get_meet_service(user)

    try:

        # Google Meet API allows the meeting code
        # to be used as a space alias.
        space_alias = (
            f"spaces/{meeting_code}"
        )

        response = (
            service.spaces()
            .get(
                name=space_alias
            )
            .execute()
        )

        space_name = response.get(
            "name"
        )

        if not space_name:

            return {
                "success": False,
                "space_name": None,
                "message": (
                    "Google Meet returned the space "
                    "but no space resource name was found."
                )
            }

        print("\n===================================")
        print("GOOGLE MEET SPACE FOUND")
        print("MEETING CODE:", meeting_code)
        print("SPACE NAME:", space_name)
        print("===================================")

        return {
            "success": True,
            "space_name": space_name,
            "space": response,
        }

    except Exception as e:

        print("\n===================================")
        print("GOOGLE MEET SPACE ERROR")
        print("MEETING CODE:", meeting_code)
        print("ERROR:", e)
        print("===================================")

        return {
            "success": False,
            "space_name": None,
            "message": str(e),
        }

# =========================================================
# AUTO RECORDING
# =========================================================

def set_auto_recording(
    meeting,
    user,
    enabled=True
):
    """
    Enable or disable automatic recording for the
    Google Meet space belonging to this Meeting.

    IMPORTANT:
    Google Meet requires the actual space resource
    name, for example:

        spaces/abc123

    Therefore Meeting.space_name must be populated.
    """

    # -----------------------------------------------------
    # Get the Google Meet space name
    # -----------------------------------------------------

    space_name = meeting.space_name

    if not space_name:

        print(
            "AUTO RECORDING ERROR: "
            "Google Meet space name is not available."
        )

        return {
            "success": False,
            "enabled": enabled,
            "message": (
                "Google Meet space name is not available. "
                "The meeting was created without saving "
                "the Google Meet space resource."
            ),
        }

    # -----------------------------------------------------
    # Get Meet API service
    # -----------------------------------------------------

    service = get_meet_service(user)

    # -----------------------------------------------------
    # Google Meet recording state
    # -----------------------------------------------------

    recording_state = (
        "ON"
        if enabled
        else "OFF"
    )

    # -----------------------------------------------------
    # Request body
    # -----------------------------------------------------

    request_body = {
        "config": {
            "artifactConfig": {
                "recordingConfig": {
                    "autoRecordingGeneration": recording_state
                }
            }
        }
    }

    print("\n===================================")
    print("UPDATING AUTO RECORDING")
    print("MEETING:", meeting.meeting_title)
    print("MEETING CODE:", meeting.meeting_code)
    print("SPACE:", space_name)
    print("ENABLED:", enabled)
    print("===================================")

    try:

        response = (
            service.spaces()
            .patch(
                name=space_name,
                updateMask=(
                    "config.artifactConfig."
                    "recordingConfig.autoRecordingGeneration"
                ),
                body=request_body
            )
            .execute()
        )

        # -------------------------------------------------
        # Google accepted the change
        # -------------------------------------------------

        meeting.auto_record = enabled

        meeting.save(
            update_fields=[
                "auto_record"
            ]
        )

        print("\n===================================")
        print("AUTO RECORDING UPDATED SUCCESSFULLY")
        print("MEETING:", meeting.meeting_title)
        print("SPACE:", space_name)
        print("ENABLED:", enabled)
        print("===================================")

        return {
            "success": True,
            "enabled": enabled,
            "space": response,
        }

    except Exception as e:

        print("\n===================================")
        print("AUTO RECORDING ERROR")
        print("SPACE:", space_name)
        print("ERROR:", e)
        print("===================================")

        return {
            "success": False,
            "enabled": enabled,
            "message": str(e),
        }


# =========================================================
# GOOGLE DRIVE SERVICE
# =========================================================

def get_drive_service(user):

    credentials = get_google_credentials(user)

    service = build(
        "drive",
        "v3",
        credentials=credentials
    )

    return service


# =========================================================
# GOOGLE PEOPLE API SERVICE
# =========================================================

def get_people_service(user):

    credentials = get_google_credentials(user)

    service = build(
        "people",
        "v1",
        credentials=credentials
    )

    return service


# =========================================================
# GET PARTICIPANT EMAIL
# =========================================================

def get_participant_email(
    participant_google_user,
    user
):
    """
    Retrieve the email address of a signed-in
    Google Meet participant using the People API.
    """

    if not participant_google_user:
        return None

    # Google Meet gives:
    #
    # users/123456789
    #
    # People API expects:
    #
    # people/123456789

    person_id = participant_google_user.replace(
        "users/",
        "",
        1
    )

    person_resource = (
        f"people/{person_id}"
    )

    service = get_people_service(user)

    try:

        response = (
            service.people()
            .get(
                resourceName=person_resource,
                personFields="names,emailAddresses",
                sources=[
                    "READ_SOURCE_TYPE_PROFILE",
                    "READ_SOURCE_TYPE_CONTACT",
                    "READ_SOURCE_TYPE_OTHER_CONTACT",
                ],
            )
            .execute()
        )

        print(
            "PEOPLE API RESPONSE:",
            json.dumps(
                response,
                indent=2
            )
        )

    except Exception as e:

        print(
            "PEOPLE API ERROR:",
            participant_google_user,
            e
        )

        return None

    email_addresses = response.get(
        "emailAddresses",
        []
    )

    if not email_addresses:
        return None

    for email_data in email_addresses:

        email = email_data.get(
            "value"
        )

        if email:
            return email

    return None


# =========================================================
# DATE/TIME HELPER
# =========================================================

def parse_google_datetime(value):
    """
    Convert Google's ISO-8601 timestamp into
    a Python datetime.
    """

    if not value:
        return None

    return datetime.fromisoformat(
        value.replace(
            "Z",
            "+00:00"
        )
    )


# =========================================================
# PARTICIPANT DURATION HELPER
# =========================================================

def calculate_merged_duration(sessions):
    """
    Calculate total participant attendance duration
    without double-counting overlapping sessions.

    Example:

        10:00 - 10:30
        10:15 - 10:45

    Result:

        45 minutes
    """

    intervals = []

    for session in sessions:

        if (
            not session.joined_at
            or not session.left_at
        ):
            continue

        intervals.append(
            (
                session.joined_at,
                session.left_at
            )
        )

    if not intervals:
        return timedelta(0)

    intervals.sort(
        key=lambda interval: interval[0]
    )

    merged_intervals = []

    current_start, current_end = (
        intervals[0]
    )

    for start, end in intervals[1:]:

        if start <= current_end:

            if end > current_end:
                current_end = end

        else:

            merged_intervals.append(
                (
                    current_start,
                    current_end
                )
            )

            current_start = start
            current_end = end

    merged_intervals.append(
        (
            current_start,
            current_end
        )
    )

    total_duration = timedelta(0)

    for start, end in merged_intervals:

        total_duration += (
            end - start
        )

    return total_duration


# =========================================================
# TEST: LIST ALL CONFERENCES
# =========================================================

def test_list_conferences(user):

    service = get_meet_service(user)

    response = (
        service.conferenceRecords()
        .list(
            pageSize=100
        )
        .execute()
    )

    return response


# =========================================================
# TEST: LIST PARTICIPANTS
# =========================================================

def test_list_participants(
    conference_record_name,
    user
):

    service = get_meet_service(user)

    response = (
        service.conferenceRecords()
        .participants()
        .list(
            parent=conference_record_name,
            pageSize=100,
        )
        .execute()
    )

    return response


# =========================================================
# TEST: LIST PARTICIPANT SESSIONS
# =========================================================

def test_list_participant_sessions(
    participant_name,
    user
):

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


# =========================================================
# FIND ALL CONFERENCE RECORDS FOR A MEETING
# =========================================================

def find_conference_records_for_meeting(
    meeting,
    user
):
    """
    Find ALL Google Meet conference records belonging
    to this Meeting's Google Meet space.

    One Meeting can have multiple Conference records.
    """

    service = get_meet_service(user)

    print("\n===================================")
    print("SEARCHING FOR CONFERENCES")
    print("MEETING:", meeting.meeting_title)
    print("MEETING CODE:", meeting.meeting_code)
    print("SPACE:", meeting.space_name)
    print("===================================")

    # -----------------------------------------------------
    # Prefer the actual space resource if available.
    # -----------------------------------------------------

    if meeting.space_name:

        filter_value = (
            f'space.name = "{meeting.space_name}"'
        )

    elif meeting.meeting_code:

        filter_value = (
            f'space.meeting_code = '
            f'"{meeting.meeting_code}"'
        )

    else:

        print(
            "No meeting code or space name available."
        )

        return []

    try:

        response = (
            service.conferenceRecords()
            .list(
                pageSize=100,
                filter=filter_value,
            )
            .execute()
        )

    except Exception as e:

        print(
            "CONFERENCE SEARCH ERROR:",
            e
        )

        return []

    conferences = response.get(
        "conferenceRecords",
        []
    )

    print(
        "GOOGLE CONFERENCES FOUND:",
        len(conferences)
    )

    # -----------------------------------------------------
    # Sort oldest → newest
    # -----------------------------------------------------

    conferences.sort(
        key=lambda conference: (
            conference.get(
                "startTime",
                ""
            )
        )
    )

    for index, conference_data in enumerate(
        conferences,
        start=1
    ):

        print("\n===================================")
        print(
            f"CONFERENCE {index}"
        )
        print(
            "CONFERENCE:",
            conference_data.get("name")
        )
        print(
            "SPACE:",
            conference_data.get("space")
        )
        print(
            "START:",
            conference_data.get("startTime")
        )
        print(
            "END:",
            conference_data.get("endTime")
        )
        print("===================================")

    return conferences


# =========================================================
# SAVE / UPDATE CONFERENCE
# =========================================================

def save_conference(
    meeting,
    conference_data
):
    """
    Create or update one Conference database record.
    """

    conference_record_name = (
        conference_data.get("name")
    )

    if not conference_record_name:
        return None

    space_name = (
        conference_data.get("space")
    )

    start_time = parse_google_datetime(
        conference_data.get("startTime")
    )

    end_time = parse_google_datetime(
        conference_data.get("endTime")
    )

    duration = None

    if start_time and end_time:

        duration = (
            end_time - start_time
        )

    conference, created = (
        Conference.objects.update_or_create(
            conference_record=conference_record_name,
            defaults={
                "meeting": meeting,
                "space": space_name,
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
            },
        )
    )

    print("\n-----------------------------------")
    print(
        "CONFERENCE SAVED:",
        conference.id
    )
    print(
        "CONFERENCE RECORD:",
        conference.conference_record
    )
    print(
        "START:",
        conference.start_time
    )
    print(
        "END:",
        conference.end_time
    )
    print(
        "DURATION:",
        conference.duration
    )
    print(
        "CREATED:",
        created
    )
    print("-----------------------------------")

    return conference


# =========================================================
# SYNC CONFERENCE PARTICIPANTS
# =========================================================

def sync_conference_participants(
    conference,
    user
):
    """
    Fetch and save all participants belonging
    to one specific Conference.
    """

    service = get_meet_service(user)

    conference_record_name = (
        conference.conference_record
    )

    response = (
        service.conferenceRecords()
        .participants()
        .list(
            parent=conference_record_name,
            pageSize=100,
        )
        .execute()
    )

    participants = response.get(
        "participants",
        []
    )

    print("\n===================================")
    print(
        "CONFERENCE PARTICIPANTS:",
        conference_record_name
    )
    print(
        "PARTICIPANTS FOUND:",
        len(participants)
    )
    print("===================================")

    participant_count = 0
    session_count = 0

    for participant_data in participants:

        print("\n========== PARTICIPANT ==========")

        print(
            json.dumps(
                participant_data,
                indent=2
            )
        )

        participant_resource = (
            participant_data.get("name")
        )

        if not participant_resource:
            continue

        # -------------------------------------------------
        # SIGNED-IN USER
        # -------------------------------------------------

        user_data = (
            participant_data.get(
                "signedinUser"
            )
            or participant_data.get(
                "signedInUser"
            )
        )

        participant_name = None
        participant_google_user = None

        if user_data:

            participant_name = (
                user_data.get(
                    "displayName"
                )
            )

            participant_google_user = (
                user_data.get(
                    "user"
                )
            )

        # -------------------------------------------------
        # EMAIL
        # -------------------------------------------------

        participant_email = (
            get_participant_email(
                participant_google_user,
                user
            )
        )

        print(
            "PARTICIPANT EMAIL:",
            participant_email
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
        # CREATE / UPDATE PARTICIPANT
        # -------------------------------------------------

        lookup = {
            "conference": conference,
        }

        if participant_google_user:

            lookup["google_user"] = (
                participant_google_user
            )

        else:

            lookup["participant_resource"] = (
                participant_resource
            )

        participant, created = (
            ParticipantAttendance.objects
            .update_or_create(
                **lookup,
                defaults={
                    "participant_name":
                        participant_name,

                    "participant_email":
                        participant_email,

                    "participant_resource":
                        participant_resource,
                },
            )
        )

        participant_count += 1

        print(
            "PARTICIPANT DB ID:",
            participant.id
        )

        # -------------------------------------------------
        # GET PARTICIPANT SESSIONS
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

        sessions = (
            sessions_response.get(
                "participantSessions",
                []
            )
        )

        print(
            "SESSIONS FOUND:",
            len(sessions)
        )

        # -------------------------------------------------
        # SAVE SESSIONS
        # -------------------------------------------------

        for session_data in sessions:

            session_resource = (
                session_data.get("name")
            )

            joined_at = (
                parse_google_datetime(
                    session_data.get(
                        "startTime"
                    )
                )
            )

            left_at = (
                parse_google_datetime(
                    session_data.get(
                        "endTime"
                    )
                )
            )

            if (
                not session_resource
                or not joined_at
            ):
                continue

            duration = None

            if joined_at and left_at:

                duration = (
                    left_at - joined_at
                )

            session, created = (
                ParticipantSession.objects
                .update_or_create(
                    session_resource=session_resource,
                    defaults={
                        "participant":
                            participant,

                        "joined_at":
                            joined_at,

                        "left_at":
                            left_at,

                        "duration":
                            duration,
                    },
                )
            )

            session_count += 1

            print(
                "SESSION:",
                session_resource
            )

            print(
                "JOINED:",
                joined_at
            )

            print(
                "LEFT:",
                left_at
            )

            print(
                "DURATION:",
                duration
            )

        # -------------------------------------------------
        # UPDATE PARTICIPANT SUMMARY
        # -------------------------------------------------

        all_sessions = (
            ParticipantSession.objects
            .filter(
                participant=participant
            )
        )

        participant.first_joined = (
            all_sessions
            .order_by("joined_at")
            .values_list(
                "joined_at",
                flat=True
            )
            .first()
        )

        participant.last_left = (
            all_sessions
            .exclude(
                left_at=None
            )
            .order_by("-left_at")
            .values_list(
                "left_at",
                flat=True
            )
            .first()
        )

        participant.total_duration = (
            calculate_merged_duration(
                all_sessions
            )
        )

        participant.save(
            update_fields=[
                "first_joined",
                "last_left",
                "total_duration",
            ]
        )

        print(
            "TOTAL PARTICIPANT DURATION:",
            participant.total_duration
        )

    return {
        "participants": participant_count,
        "sessions": session_count,
    }

# =========================================================
# SYNC CONFERENCE RECORDINGS
# =========================================================

def sync_conference_recordings(
    conference,
    user
):
    """
    Retrieve all Google Meet recordings belonging to
    one specific Conference record.

    Google Meet:
        Conference
            ↓
        Recordings
            ↓
        Google Drive file
    """

    service = get_meet_service(user)

    conference_record_name = (
        conference.conference_record
    )

    print("\n===================================")
    print("CHECKING CONFERENCE RECORDINGS")
    print("CONFERENCE:", conference_record_name)
    print("===================================")

    try:

        response = (
            service.conferenceRecords()
            .recordings()
            .list(
                parent=conference_record_name,
                pageSize=100,
            )
            .execute()
        )

    except Exception as e:

        print(
            "RECORDING API ERROR:",
            e
        )

        return {
            "success": False,
            "recordings": 0,
            "message": str(e),
        }

    recordings = response.get(
        "recordings",
        []
    )

    print(
        "RECORDINGS FOUND:",
        len(recordings)
    )

    recording_count = 0

    for recording_data in recordings:

        print("\n========== RECORDING ==========")

        print(
            json.dumps(
                recording_data,
                indent=2
            )
        )

        recording_resource = recording_data.get(
            "name"
        )

        if not recording_resource:
            continue

        # -------------------------------------------------
        # Recording time
        # -------------------------------------------------

        start_time = parse_google_datetime(
            recording_data.get(
                "startTime"
            )
        )

        end_time = parse_google_datetime(
            recording_data.get(
                "endTime"
            )
        )

        # -------------------------------------------------
        # Google Drive destination
        # -------------------------------------------------

        drive_destination = (
            recording_data.get(
                "driveDestination",
                {}
            )
        )

        drive_file_id = (
            drive_destination.get(
                "file"
            )
        )

        recording_url = (
            drive_destination.get(
                "exportUri"
            )
        )

        # -------------------------------------------------
        # Save recording
        # -------------------------------------------------

        recording, created = (
            ConferenceRecording.objects.update_or_create(
                recording_resource=recording_resource,
                defaults={
                    "conference": conference,
                    "start_time": start_time,
                    "end_time": end_time,
                    "drive_file_id": drive_file_id,
                    "recording_url": recording_url,
                },
            )
        )

        recording_count += 1

        print(
            "RECORDING DB ID:",
            recording.id
        )

        print(
            "RECORDING RESOURCE:",
            recording_resource
        )

        print(
            "START:",
            start_time
        )

        print(
            "END:",
            end_time
        )

        print(
            "DRIVE FILE ID:",
            drive_file_id
        )

        print(
            "RECORDING URL:",
            recording_url
        )

        print(
            "CREATED:",
            created
        )

    return {
        "success": True,
        "recordings": recording_count,
        "message": (
            "Conference recordings synchronized."
        ),
    }

# =========================================================
# MAIN ATTENDANCE SYNCHRONIZATION
# =========================================================

def sync_meeting_attendance(
    meeting_id,
    user
):
    """
    Synchronize ALL Google Meet conference records
    belonging to one Meeting.

    For each conference:

        Conference
            ├── Participants
            │      └── Sessions
            │
            └── Recordings
    """

    meeting = Meeting.objects.get(
        id=meeting_id
    )

    print("\n")
    print("==============================================")
    print("STARTING MEETING SYNCHRONIZATION")
    print("==============================================")
    print(
        "MEETING:",
        meeting.meeting_title
    )
    print(
        "MEETING CODE:",
        meeting.meeting_code
    )
    print(
        "SPACE:",
        meeting.space_name
    )
    print("==============================================")

    # -----------------------------------------------------
    # 1. FIND ALL CONFERENCES
    # -----------------------------------------------------

    conferences = (
        find_conference_records_for_meeting(
            meeting,
            user
        )
    )

    if not conferences:

        return {
            "success": False,
            "message": (
                "No Google Meet conference records "
                "were found for this meeting."
            ),
            "conferences": 0,
            "participants": 0,
            "sessions": 0,
            "recordings": 0,
        }

    total_participants = 0
    total_sessions = 0
    total_recordings = 0

    saved_conferences = []

    # -----------------------------------------------------
    # 2. PROCESS EVERY CONFERENCE
    # -----------------------------------------------------

    for index, conference_data in enumerate(
        conferences,
        start=1
    ):

        print("\n")
        print("##############################################")
        print(
            f"PROCESSING CONFERENCE {index}"
        )
        print("##############################################")

        # -------------------------------------------------
        # Save Conference
        # -------------------------------------------------

        conference = save_conference(
            meeting,
            conference_data
        )

        if not conference:
            continue

        saved_conferences.append(
            conference
        )

        # -------------------------------------------------
        # Participants + Sessions
        # -------------------------------------------------

        participant_result = (
            sync_conference_participants(
                conference,
                user
            )
        )

        total_participants += (
            participant_result[
                "participants"
            ]
        )

        total_sessions += (
            participant_result[
                "sessions"
            ]
        )

        # -------------------------------------------------
        # Recordings
        # -------------------------------------------------

        recording_result = (
            sync_conference_recordings(
                conference,
                user
            )
        )

        total_recordings += (
            recording_result[
                "recordings"
            ]
        )

    # -----------------------------------------------------
    # 3. FINAL RESULT
    # -----------------------------------------------------

    print("\n")
    print("==============================================")
    print("MEETING SYNCHRONIZATION COMPLETE")
    print("==============================================")
    print(
        "CONFERENCES:",
        len(saved_conferences)
    )
    print(
        "PARTICIPANTS:",
        total_participants
    )
    print(
        "SESSIONS:",
        total_sessions
    )
    print(
        "RECORDINGS:",
        total_recordings
    )
    print("==============================================")

    return {
        "success": True,
        "message": (
            "Meeting attendance synchronized successfully."
        ),
        "meeting_id": meeting.id,
        "meeting_title": meeting.meeting_title,
        "meeting_code": meeting.meeting_code,
        "conferences": len(saved_conferences),
        "participants": total_participants,
        "sessions": total_sessions,
        "recordings": total_recordings,
    }


# =========================================================
# GET MEETING RECORDING
# =========================================================

def get_meeting_recording(
    meeting_id,
    user
):
    """
    Find recordings for all conferences belonging
    to a Meeting.

    Recordings are stored in ConferenceRecording.
    """

    meeting = Meeting.objects.get(
        id=meeting_id,
        user=user
    )

    conferences = (
        Conference.objects
        .filter(
            meeting=meeting
        )
        .order_by(
            "start_time"
        )
    )

    if not conferences.exists():

        return {
            "success": False,
            "message": (
                "No conferences have been synchronized "
                "for this meeting yet."
            ),
            "recordings": [],
        }

    service = get_meet_service(user)

    all_recordings = []

    for conference in conferences:

        conference_record_name = (
            conference.conference_record
        )

        print("\n===================================")
        print(
            "GETTING RECORDINGS FOR:",
            conference_record_name
        )
        print("===================================")

        response = (
            service.conferenceRecords()
            .recordings()
            .list(
                parent=conference_record_name,
                pageSize=100,
            )
            .execute()
        )

        recordings = response.get(
            "recordings",
            []
        )

        for recording_data in recordings:

            recording_resource = (
                recording_data.get("name")
            )

            if not recording_resource:
                continue

            start_time = (
                parse_google_datetime(
                    recording_data.get(
                        "startTime"
                    )
                )
            )

            end_time = (
                parse_google_datetime(
                    recording_data.get(
                        "endTime"
                    )
                )
            )

            drive_destination = (
                recording_data.get(
                    "driveDestination",
                    {}
                )
            )

            drive_file_id = (
                drive_destination.get(
                    "file"
                )
            )

            recording_url = (
                drive_destination.get(
                    "exportUri"
                )
            )

            recording, created = (
                ConferenceRecording.objects
                .update_or_create(
                    recording_resource=recording_resource,
                    defaults={
                        "conference":
                            conference,

                        "start_time":
                            start_time,

                        "end_time":
                            end_time,

                        "drive_file_id":
                            drive_file_id,

                        "recording_url":
                            recording_url,
                    },
                )
            )

            all_recordings.append(
                recording
            )

            print(
                "RECORDING:",
                recording_resource
            )

            print(
                "DRIVE FILE:",
                drive_file_id
            )

            print(
                "URL:",
                recording_url
            )

    if not all_recordings:

        return {
            "success": False,
            "message": (
                "No recordings were found for "
                "the conferences of this meeting."
            ),
            "recordings": [],
        }

    return {
        "success": True,
        "message": (
            "Recordings found and synchronized successfully."
        ),
        "recordings": [
            {
                "id": recording.id,

                "conference_id":
                    recording.conference.id,

                "recording_resource":
                    recording.recording_resource,

                "drive_file_id":
                    recording.drive_file_id,

                "recording_url":
                    recording.recording_url,

                "start_time":
                    recording.start_time,

                "end_time":
                    recording.end_time,
            }
            for recording in all_recordings
        ],
    }