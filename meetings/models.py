from django.db import models
from django.contrib.auth.models import User


class GoogleCredentials(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="google_credentials",
        null=True,
        blank=True
    )

    access_token = models.TextField()
    refresh_token = models.TextField()

    token_expiry = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"Google Credentials - {self.user.username}"


class Meeting(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="meetings",
        null=True,
        blank=True
    )

    meeting_title = models.CharField(
        max_length=255
    )

    gmeet_link = models.URLField()

    # Google Meet meeting code
    meeting_code = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    # Google Meet space resource
    space_name = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    # ---------------------------------------------
    # AUTO RECORDING
    # ---------------------------------------------

    auto_record = models.BooleanField(
        default=False
    )

    # -------------------------------------------------
    # SCHEDULED MEETING TIME
    # -------------------------------------------------

    start_time = models.DateTimeField()

    end_time = models.DateTimeField(
        null=True,
        blank=True
    )

    duration = models.DurationField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def save(self, *args, **kwargs):

        if self.start_time and self.end_time:
            self.duration = (
                self.end_time - self.start_time
            )

        super().save(*args, **kwargs)

    def __str__(self):
        return self.meeting_title


class Conference(models.Model):

    meeting = models.ForeignKey(
        Meeting,
        on_delete=models.CASCADE,
        related_name="conferences"
    )

    # Google Meet conference record
    conference_record = models.CharField(
        max_length=255,
        unique=True
    )

    # Google Meet space
    space = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    # -------------------------------------------------
    # ACTUAL CONFERENCE TIME
    # -------------------------------------------------

    start_time = models.DateTimeField()

    end_time = models.DateTimeField(
        null=True,
        blank=True
    )

    duration = models.DurationField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def save(self, *args, **kwargs):

        if self.start_time and self.end_time:
            self.duration = (
                self.end_time - self.start_time
            )

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.meeting.meeting_title} - "
            f"{self.start_time}"
        )


class MeetingParticipant(models.Model):

    meeting = models.ForeignKey(
        Meeting,
        on_delete=models.CASCADE,
        related_name="invited_participants"
    )

    email = models.EmailField()

    def __str__(self):
        return self.email


class ParticipantAttendance(models.Model):

    conference = models.ForeignKey(
        Conference,
        on_delete=models.CASCADE,
        related_name="participants"
    )

    participant_name = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    participant_email = models.EmailField(
        blank=True,
        null=True
    )

    # Google signed-in user ID
    google_user = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    # Google Meet participant resource
    participant_resource = models.CharField(
        max_length=500,
        blank=True,
        null=True
    )

    # First time this participant joined
    first_joined = models.DateTimeField(
        null=True,
        blank=True
    )

    # Last time this participant left
    last_left = models.DateTimeField(
        null=True,
        blank=True
    )

    # Total attendance across sessions
    total_duration = models.DurationField(
        null=True,
        blank=True
    )

    def __str__(self):
        return (
            self.participant_name
            or self.participant_email
            or "Unknown participant"
        )


class ParticipantSession(models.Model):

    participant = models.ForeignKey(
        ParticipantAttendance,
        on_delete=models.CASCADE,
        related_name="sessions"
    )

    # Google Meet participant session resource
    session_resource = models.CharField(
        max_length=255,
        unique=True
    )

    joined_at = models.DateTimeField()

    left_at = models.DateTimeField(
        null=True,
        blank=True
    )

    duration = models.DurationField(
        null=True,
        blank=True
    )

    def save(self, *args, **kwargs):

        if self.joined_at and self.left_at:
            self.duration = (
                self.left_at - self.joined_at
            )

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.joined_at} - {self.left_at}"


class ConferenceRecording(models.Model):

    conference = models.ForeignKey(
        Conference,
        on_delete=models.CASCADE,
        related_name="recordings"
    )

    # Google Meet recording resource
    recording_resource = models.CharField(
        max_length=255,
        unique=True
    )

    start_time = models.DateTimeField(
        null=True,
        blank=True
    )

    end_time = models.DateTimeField(
        null=True,
        blank=True
    )

    # Google Drive file ID
    drive_file_id = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    # Google Drive playback URL
    recording_url = models.URLField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return (
            f"Recording - "
            f"{self.conference}"
        )