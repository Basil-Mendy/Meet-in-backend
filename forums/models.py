import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from .utils import calculate_ring
import random
import string


User = settings.AUTH_USER_MODEL


def generate_forum_id():
    """Generate a unique forum ID"""
    forum_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return forum_id


class Forum(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    forum_id = models.CharField(max_length=20, unique=True, null=True, blank=True)  # Public forum ID for searches
    name = models.CharField(max_length=150)
    description = models.TextField()
    address = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    
    # Profile completion fields
    profile_picture = models.ImageField(upload_to="forum_logos/", null=True, blank=True)
    slogan = models.CharField(max_length=255, blank=True)
    motto = models.TextField(blank=True)
    registration_details = models.TextField(blank=True)
    registration_certificate = models.FileField(upload_to="forum_certs/", null=True, blank=True)
    constitution = models.FileField(upload_to="forum_docs/", null=True, blank=True)
    objectives_rules = models.TextField(blank=True, help_text="Forum objectives and rules")
    
    # Legacy field, kept for compatibility
    logo = models.ImageField(upload_to="forum_logos/", null=True, blank=True)
    
    # Profile completion status
    is_completed = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_searchable = models.BooleanField(default=True, help_text="Allow forum to appear in searches")
    
    # Invitation system
    invitation_link = models.URLField(blank=True)  # Auto-generated upon creation
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_forums")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class ForumMembership(models.Model):
    ROLE_CHOICES = [
        ("SA", "Sole Admin"),
        ("CP", "Chairperson"),
        ("VC", "Vice Chairperson"),
        ("SEC", "Secretary"),
        ("FSEC", "Financial Secretary"),
        ("PRO1", "Provost 1"),
        ("PRO2", "Provost 2"),
        ("PRO3", "Provost 3"),
        ("MEMBER", "Member"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="MEMBER")
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("user", "forum")

    def __str__(self):
        return f"{self.user} - {self.forum}"


class ForumEmailSettings(models.Model):
    """Optional separate model for forum email configuration.

    This keeps sensitive configuration separate and easier to manage.
    """
    forum = models.OneToOneField(Forum, on_delete=models.CASCADE, related_name="email_settings")
    email_address = models.EmailField(blank=True, null=True)
    EMAIL_PROVIDER_GOOGLE = "google"
    EMAIL_PROVIDER_MICROSOFT = "microsoft"
    EMAIL_PROVIDER_SMTP = "smtp"
    EMAIL_PROVIDER_CHOICES = [
        (EMAIL_PROVIDER_GOOGLE, "Google (OAuth2)"),
        (EMAIL_PROVIDER_MICROSOFT, "Microsoft (OAuth2)"),
        (EMAIL_PROVIDER_SMTP, "SMTP"),
    ]
    email_provider = models.CharField(max_length=20, choices=EMAIL_PROVIDER_CHOICES, null=True, blank=True)

    # Encrypted blobs (store encrypted JSON) - actual encryption handled in service layer
    oauth_tokens = models.JSONField(null=True, blank=True)
    smtp_config = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Email settings for {self.forum.name}"


class MemberActivity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    membership = models.OneToOneField(
        ForumMembership,
        on_delete=models.CASCADE,
        related_name="activity"
    )
    meetings_attended = models.IntegerField(default=0)
    payments_completed = models.IntegerField(default=0)
    chats_sent = models.IntegerField(default=0)
    last_active = models.DateTimeField(auto_now=True)
    activity_score = models.IntegerField(default=0)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Only update ring if it exists (not during initial creation)
        if hasattr(self.membership, 'ring'):
            ring = self.membership.ring
            new_color = calculate_ring(self.activity_score)

            if ring.ring_color != new_color:
                ring.ring_color = new_color
                ring.save()



class ProfileRing(models.Model):
    RING_CHOICES = [
        ("GRAY", "Gray"),
        ("BRONZE", "Bronze"),
        ("SILVER", "Silver"),
        ("GOLD", "Gold"),
        ("PLATINUM", "Platinum"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    membership = models.OneToOneField(ForumMembership, on_delete=models.CASCADE, related_name="ring")
    ring_color = models.CharField(max_length=10, choices=RING_CHOICES, default="GRAY")
    updated_at = models.DateTimeField(auto_now=True)


class ForumJoinRequest(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="forum_join_requests")
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE, related_name="join_requests")
    invitation_code = models.CharField(max_length=100, blank=True)  # Code used for joining
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_join_requests")

    class Meta:
        unique_together = ("user", "forum")
        ordering = ["-requested_at"]

    def __str__(self):
        return f"{self.user} -> {self.forum} ({self.status})"


class ForumInvitationCode(models.Model):
    USAGE_TYPE_CHOICES = [
        ("SINGLE", "Single Use"),
        ("MULTIPLE", "Multiple Uses"),
        ("LIMITED", "Limited Uses"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE, related_name="invitation_codes")
    code = models.CharField(max_length=50, unique=True)
    usage_type = models.CharField(max_length=10, choices=USAGE_TYPE_CHOICES, default="MULTIPLE")
    max_usage_count = models.IntegerField(null=True, blank=True)  # For LIMITED type
    current_usage_count = models.IntegerField(default=0)
    valid_from = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateTimeField()  # Code expires after this time
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_invitation_codes")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.forum} - {self.code}"

    def can_be_used(self):
        """Check if code is still valid"""
        from django.utils import timezone
        if not self.is_active:
            return False
        if timezone.now() > self.valid_until:
            return False
        if self.usage_type == "SINGLE" and self.current_usage_count >= 1:
            return False
        if self.usage_type == "LIMITED" and self.current_usage_count >= self.max_usage_count:
            return False
        return True

# ==================== FORUM POSTS ====================
class ForumPost(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE, related_name="posts")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="forum_posts")
    content = models.TextField()
    image = models.ImageField(upload_to="forum_posts/", null=True, blank=True)
    video = models.URLField(null=True, blank=True, help_text="URL to video")
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.author} - {self.forum}"


class PostReaction(models.Model):
    REACTION_CHOICES = [
        ("LIKE", "Like"),
        ("DISLIKE", "Dislike"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(ForumPost, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reaction_type = models.CharField(max_length=10, choices=REACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("post", "user")

    def __str__(self):
        return f"{self.user} - {self.reaction_type} on {self.post}"


class PostComment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(ForumPost, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.author} - {self.post}"


class PostCommentReply(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    comment = models.ForeignKey(PostComment, on_delete=models.CASCADE, related_name="replies")
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.author} - Reply to {self.comment}"


# ==================== FORUM MEETINGS ====================
class Meeting(models.Model):
    MEETING_TYPE_CHOICES = [
        ("VIRTUAL", "Virtual"),
        ("PHYSICAL", "Physical"),
    ]
    
    STATUS_CHOICES = [
        ("UPCOMING", "Upcoming"),
        ("LIVE", "Live"),
        ("PAST", "Past"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE, related_name="meetings")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_meetings")
    
    # Meeting details
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    meeting_type = models.CharField(max_length=20, choices=MEETING_TYPE_CHOICES)
    venue = models.CharField(max_length=255, blank=True, help_text="Required for physical meetings, optional for virtual")
    
    # Timing (manually controlled, not auto-ending)
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    actual_end = models.DateTimeField(null=True, blank=True, help_text="Admin-set end time (overrides scheduled_end)")
    
    # Participant control
    allowed_participants = models.ManyToManyField(
        User, 
        blank=True, 
        related_name="allowed_meetings",
        help_text="If empty, all forum members can join. If populated, only these users can join."
    )
    is_all_members_allowed = models.BooleanField(default=True, help_text="If True, all forum members can join. If False, only allowed_participants can join.")
    
    # Room access
    room_id = models.CharField(max_length=50, unique=True)  # Unique identifier for virtual meeting room
    
    # Status & Tracking
    is_live = models.BooleanField(default=False)
    is_cancelled = models.BooleanField(default=False)
    cancelled_reason = models.TextField(blank=True)
    
    # Minutes & Documentation
    minutes_pdf = models.FileField(upload_to="meeting_minutes/", null=True, blank=True)
    minutes_uploaded_at = models.DateTimeField(null=True, blank=True)
    minutes_uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="uploaded_meeting_minutes")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-scheduled_start"]
        indexes = [
            models.Index(fields=["forum", "-scheduled_start"]),
            models.Index(fields=["is_live"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.forum}"
    
    @property
    def status(self):
        """Calculate meeting status based on current time"""
        from django.utils import timezone
        now = timezone.now()
        
        if self.is_cancelled:
            return "CANCELLED"
        elif now >= (self.actual_end or self.scheduled_end):
            return "PAST"
        elif now >= self.scheduled_start and now < (self.actual_end or self.scheduled_end):
            return "LIVE"
        else:
            return "UPCOMING"
    
    def get_current_end_time(self):
        """Returns actual_end if admin extended, otherwise scheduled_end"""
        return self.actual_end or self.scheduled_end


class MeetingParticipant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Participation tracking
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(default=0, help_text="Time spent in meeting in seconds")
    
    # Connection status
    is_currently_active = models.BooleanField(default=True)
    last_heartbeat = models.DateTimeField(auto_now=True)
    
    # Attendance marking (for virtual meetings, auto-calculated; for physical, admin-set)
    is_marked_present = models.BooleanField(default=False, help_text="Was user present for sufficient duration?")
    presence_percentage = models.FloatField(default=0.0, help_text="Percentage of meeting time attended (0-100)")

    class Meta:
        unique_together = ("meeting", "user")
        indexes = [
            models.Index(fields=["meeting", "is_currently_active"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.meeting.title}"
    
    def calculate_attendance(self, meeting_duration_seconds):
        """Calculate if user met minimum presence threshold (30%)"""
        if meeting_duration_seconds > 0:
            self.presence_percentage = (self.duration_seconds / meeting_duration_seconds) * 100
            self.is_marked_present = self.presence_percentage >= 30.0
        else:
            self.is_marked_present = False
            self.presence_percentage = 0.0


class MeetingMinute(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.OneToOneField(Meeting, on_delete=models.CASCADE, related_name="minute")
    
    # PDF document
    pdf_file = models.FileField(upload_to="meeting_minutes/")
    
    # Tracking
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="uploaded_minutes")

    def __str__(self):
        return f"Minutes for {self.meeting.title}"


# Legacy model kept for backwards compatibility
class ForumMeeting(models.Model):
    MEETING_TYPE = [
        ("VIRTUAL", "Virtual"),
        ("PHYSICAL", "Physical"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE, related_name="forum_meetings_legacy")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_forum_meetings_legacy")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    meeting_type = models.CharField(max_length=20, choices=MEETING_TYPE)
    venue = models.CharField(max_length=255, blank=True, help_text="Physical location or virtual link")
    scheduled_at = models.DateTimeField()
    is_live = models.BooleanField(default=False)
    meeting_link = models.URLField(null=True, blank=True, help_text="For virtual meetings")
    minutes_pdf = models.FileField(upload_to="meeting_minutes/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scheduled_at"]

    def __str__(self):
        return f"{self.title} - {self.forum}"


class MeetingAttendee(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(ForumMeeting, on_delete=models.CASCADE, related_name="attendees")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("meeting", "user")

    def __str__(self):
        return f"{self.user} - {self.meeting}"


# ==================== FORUM PAYMENTS ====================
class ForumPayment(models.Model):
    PAYMENT_TYPE = [
        ("DUES", "Dues"),
        ("CONTRIBUTION", "Contribution"),
        ("LEVIES", "Levies"),
        ("DISBURSEMENT", "Disbursement"),
    ]

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("PAID", "Paid"),
    ]

    CATEGORY_CHOICES = [
        ("MALE", "Male"),
        ("FEMALE", "Female"),
        ("BELOW_18", "Below 18"),
        ("18_PLUS", "18+"),
        ("YOUTH", "Youth"),
        ("MOTHERS", "Mothers"),
        ("FATHERS", "Fathers"),
        ("JUNIOR", "Junior"),
        ("SENIOR", "Senior"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE, related_name="forum_payments")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_forum_payments")
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE)
    name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, null=True, blank=True, help_text="For levies")
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - {self.forum}"


class ForumPaymentSubmission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(ForumPayment, on_delete=models.CASCADE, related_name="submissions")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    receipt_image = models.ImageField(upload_to="payment_receipts/", null=True, blank=True)

    class Meta:
        unique_together = ("payment", "user")
        ordering = ["-payment_date"]

    def __str__(self):
        return f"{self.user} - {self.payment}"


# ==================== FORUM ANNOUNCEMENTS ====================
class Announcement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE, related_name="announcements")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} - {self.forum}"


# ==================== FORUM POLLS ====================
class PollGroup(models.Model):
    """Groups polls together (e.g., '2026 General Elections')"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE, related_name="poll_groups")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_poll_groups")
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["forum", "is_archived"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.forum}"


class Poll(models.Model):
    BALLOT_TYPE_CHOICES = [
        ("SECRET", "Secret Ballot"),
        ("OPEN", "Open Ballot"),
    ]
    
    VOTE_TYPE_CHOICES = [
        ("SINGLE", "Vote Once Only"),
        ("MULTIPLE", "Vote Multiple Times"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE, related_name="polls")
    group = models.ForeignKey(PollGroup, on_delete=models.CASCADE, related_name="polls", null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Poll details
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    
    # Configuration
    ballot_type = models.CharField(max_length=10, choices=BALLOT_TYPE_CHOICES, default="SECRET")
    vote_type = models.CharField(max_length=10, choices=VOTE_TYPE_CHOICES, default="SINGLE")
    
    # Status
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    
    # Backward compatibility
    question = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    ends_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["forum", "is_archived"]),
            models.Index(fields=["start_time", "end_time"]),
        ]

    @property
    def status(self):
        """Compute poll status: UPCOMING, ACTIVE, or CLOSED"""
        # Handle None values for start_time and end_time
        if not self.start_time or not self.end_time:
            return "CLOSED"  # Default to closed if times not set
        
        try:
            now = timezone.now()
            # Ensure start_time and end_time are timezone-aware
            start_time = self.start_time
            end_time = self.end_time
            
            # If times are naive, make them aware (assume local timezone)
            if start_time.tzinfo is None:
                start_time = timezone.make_aware(start_time)
            if end_time.tzinfo is None:
                end_time = timezone.make_aware(end_time)
            
            if now < start_time:
                return "UPCOMING"
            elif now < end_time:
                return "ACTIVE"
            else:
                return "CLOSED"
        except Exception as e:
            # If any error occurs during comparison, return CLOSED
            return "CLOSED"

    def __str__(self):
        return f"{self.title} - {self.forum}"


class PollOption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="options")
    option_text = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    
    # Backward compatibility
    text = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.option_text or self.text


class PollVote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="votes")
    option = models.ForeignKey(PollOption, on_delete=models.CASCADE, related_name="votes")
    voter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="poll_votes", null=True, blank=True)
    voted_at = models.DateTimeField(auto_now_add=True, null=True)
    
    # Backward compatibility
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name="poll_votes_alt")
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ["-voted_at"]
        indexes = [
            models.Index(fields=["poll", "voter"]),
            models.Index(fields=["option"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=['poll', 'option', 'voter'], name='unique_vote_per_user_option'),
        ]

    def __str__(self):
        voter_email = self.voter.email if self.voter else (self.user.email if self.user else "Unknown")
        return f"{voter_email} voted for {self.option}"


# ==================== FORUM DOCUMENTS & SETTINGS ====================
class ForumDocument(models.Model):
    """Documents uploaded to the About tab (available for all to download)"""
    FILE_TYPE_CHOICES = [
        ("PDF", "PDF"),
        ("IMAGE", "Image"),
        ("DOCUMENT", "Document"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to="forum_documents/")
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES, default="PDF")
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} - {self.forum}"


class ForumSettings(models.Model):
    """Extended forum configuration for About tab"""
    VISIBILITY_CHOICES = [
        ("PUBLIC", "Public"),
        ("PRIVATE", "Private"),
    ]
    
    JOIN_MODE_CHOICES = [
        ("OPEN", "Open"),
        ("REQUEST", "Request"),
        ("INVITE", "Invite"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    forum = models.OneToOneField(Forum, on_delete=models.CASCADE, related_name="settings")
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default="PUBLIC")
    join_mode = models.CharField(max_length=20, choices=JOIN_MODE_CHOICES, default="OPEN")
    payment_rules = models.TextField(blank=True)
    rules_regulations = models.TextField(blank=True)
    objectives = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Settings - {self.forum}"


class BankAccount(models.Model):
    """Bank account for forum/user withdrawals"""
    ACCOUNT_TYPE_CHOICES = [
        ("FORUM", "Forum"),
        ("PERSONAL", "Personal"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES)
    forum = models.OneToOneField(Forum, on_delete=models.CASCADE, related_name="bank_account", null=True, blank=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="bank_account", null=True, blank=True)
    
    account_holder_name = models.CharField(max_length=200)
    account_number = models.CharField(max_length=50)
    bank_name = models.CharField(max_length=150)
    bank_code = models.CharField(max_length=20, blank=True)
    
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("account_type", "forum", "user")

    def __str__(self):
        if self.forum:
            return f"{self.forum} - {self.account_number}"
        return f"{self.user} - {self.account_number}"


class Announcement(models.Model):
    ANNOUNCEMENT_TYPE_CHOICES = [
        ("FORUM", "Forum Announcement"),
        ("EMAIL", "Email Announcement"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE, related_name="announcements")
    title = models.CharField(max_length=255)
    message = models.TextField()
    announcement_type = models.CharField(max_length=20, choices=ANNOUNCEMENT_TYPE_CHOICES, default="FORUM")
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_announcements")
    created_at = models.DateTimeField(auto_now_add=True)
    
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    
    # For email announcements: whether to save to forum feed
    save_to_forum_feed = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["forum", "-created_at"]),
            models.Index(fields=["is_archived"]),
        ]

    def __str__(self):
        return f"{self.forum} - {self.title}"


class AnnouncementRecipient(models.Model):
    """Tracks email announcement recipients for audit"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name="email_recipients")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="announcement_emails_received")
    
    email_sent_at = models.DateTimeField(auto_now_add=True)
    email_delivery_status = models.CharField(
        max_length=20,
        choices=[("PENDING", "Pending"), ("SENT", "Sent"), ("FAILED", "Failed")],
        default="PENDING"
    )
    email_error = models.TextField(blank=True)

    class Meta:
        unique_together = ("announcement", "user")
        indexes = [
            models.Index(fields=["announcement"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"{self.announcement.title} → {self.user.email}"


class AnnouncementRead(models.Model):
    """Tracks who has read each forum announcement"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name="reads")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="announcement_reads")
    
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("announcement", "user")
        indexes = [
            models.Index(fields=["announcement"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"{self.user.email} read {self.announcement.title}"


class Notification(models.Model):
    """In-app notifications for users"""
    NOTIFICATION_TYPES = [
        ("FEED_NEW_POST", "New post in feed"),
        ("MEETING_CREATED", "Meeting created"),
        ("MEETING_LIVE", "Meeting is now live"),
        ("MEETING_ENDED", "Meeting has ended"),
        ("PAYMENT_CREATED", "Payment created"),
        ("DISBURSEMENT_CREATED", "Disbursement made"),
        ("MEMBER_ADDED", "New member added"),
        ("MEMBER_REMOVED", "Member removed"),
        ("MEMBER_ROLE_ASSIGNED", "Member role assigned"),
        ("MEMBER_ROLE_REMOVED", "Member role removed"),
        ("MEMBER_APPROVED", "Member approved"),
        ("FORUM_INFO_UPDATED", "Forum info updated"),
        ("ANNOUNCEMENT_CREATED", "Announcement made"),
        ("POLL_CREATED", "Poll created"),
        ("POLL_ACTIVE", "Poll is active"),
        ("POLL_CLOSED", "Poll closed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE, related_name="notifications")
    
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # Metadata for routing
    tab = models.CharField(
        max_length=50,
        choices=[
            ("feed", "Feed"),
            ("meetings", "Meetings"),
            ("payments", "Payments"),
            ("disbursements", "Disbursements"),
            ("members", "Members"),
            ("about", "About"),
            ("announcements", "Announcements"),
            ("polls", "Polls"),
            ("settings", "Settings"),
        ],
        help_text="Which tab should user be directed to"
    )
    
    object_id = models.CharField(max_length=50, blank=True, help_text="ID of related object (post, meeting, payment, etc)")
    
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "forum", "-created_at"]),
            models.Index(fields=["user", "is_read"]),
            models.Index(fields=["forum", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.get_notification_type_display()} for {self.user.email} in {self.forum.name}"


class UserNotificationPreference(models.Model):
    """User preferences for how they receive notifications"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="notification_preferences")
    
    # Global defaults (can be overridden per forum)
    feed_in_app = models.BooleanField(default=True)
    feed_push = models.BooleanField(default=True)
    feed_email = models.BooleanField(default=False)
    
    meetings_in_app = models.BooleanField(default=True)
    meetings_push = models.BooleanField(default=True)
    meetings_email = models.BooleanField(default=True)
    
    payments_in_app = models.BooleanField(default=True)
    payments_push = models.BooleanField(default=False)
    payments_email = models.BooleanField(default=True)
    
    disbursements_in_app = models.BooleanField(default=True)
    disbursements_push = models.BooleanField(default=False)
    disbursements_email = models.BooleanField(default=True)
    
    members_in_app = models.BooleanField(default=True)
    members_push = models.BooleanField(default=False)
    members_email = models.BooleanField(default=False)
    
    forum_info_in_app = models.BooleanField(default=True)
    forum_info_push = models.BooleanField(default=False)
    forum_info_email = models.BooleanField(default=False)
    
    announcements_in_app = models.BooleanField(default=True)
    announcements_push = models.BooleanField(default=True)
    announcements_email = models.BooleanField(default=True)
    
    polls_in_app = models.BooleanField(default=True)
    polls_push = models.BooleanField(default=False)
    polls_email = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "User notification preferences"

    def __str__(self):
        return f"Notification preferences for {self.user.email}"