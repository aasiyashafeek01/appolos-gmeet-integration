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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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

    meeting_title = models.CharField(max_length=255)

    gmeet_link = models.URLField()

    # Google Meet meeting code
    meeting_code = models.CharField(
        max_length=50,
        blank=True,
        null=True
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

    # -------------------------------------------------
    # ACTUAL GOOGLE MEET CONFERENCE TIME
    # -------------------------------------------------

    actual_start_time = models.DateTimeField(
        null=True,
        blank=True
    )

    actual_end_time = models.DateTimeField(
        null=True,
        blank=True
    )

    actual_duration = models.DurationField(
        null=True,
        blank=True
    )

    # -------------------------------------------------
    # PARTICIPANT / RECORDING INFORMATION
    # -------------------------------------------------

    participant_email = models.EmailField(
        blank=True,
        null=True
    )

    # Google Meet conference record
    conference_record = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    # Google Drive playback URL for recording
    recording_url = models.URLField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def save(self, *args, **kwargs):

        # Scheduled duration
        if self.start_time and self.end_time:
            self.duration = self.end_time - self.start_time

        # Actual Meet duration
        if self.actual_start_time and self.actual_end_time:
            self.actual_duration = (
                self.actual_end_time - self.actual_start_time
            )

        super().save(*args, **kwargs)

    def __str__(self):
        return self.meeting_title

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

    meeting = models.ForeignKey(
        Meeting,
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

    # Sum of all participant sessions
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
        max_length=500,
        blank=True,
        null=True
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
            self.duration = self.left_at - self.joined_at

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.joined_at} - {self.left_at}"

