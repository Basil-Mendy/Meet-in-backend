import uuid
from datetime import datetime
from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL


class School(models.Model):
    SCHOOL_TYPES = [
        ("PRIMARY", "Primary School"),
        ("SECONDARY", "Secondary School"),
        ("COLLEGE", "College"),
        ("TECHNICAL", "Technical School"),
        ("UNIVERSITY", "University"),
        ("POLYTECHNIC", "Polytechnic"),
        ("COLLEGE_OF_EDUCATION", "College of Education"),
        ("OTHER", "Other"),
    ]

    VISIBILITY_CHOICES = [
        ("PUBLIC", "Public"),
        ("PRIVATE", "Private"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    address = models.CharField(max_length=255)
    country = models.CharField(max_length=100, blank=True, default="Nigeria")
    state = models.CharField(max_length=100, blank=True)
    lga = models.CharField(max_length=100, blank=True)
    ward = models.CharField(max_length=100, blank=True)
    year_established = models.PositiveIntegerField()
    school_type = models.CharField(max_length=20, choices=SCHOOL_TYPES, default="SECONDARY")
    primary_color = models.CharField(max_length=20, default="#0f172a")
    secondary_color = models.CharField(max_length=20, default="#f59e0b")
    badge = models.ImageField(upload_to="school_badges/", null=True, blank=True)
    description = models.TextField(blank=True)
    main_contact_number = models.CharField(max_length=20, blank=True)
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default="PUBLIC")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_schools")
    is_approved = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def current_year(self):
        return datetime.now().year

    def get_years(self):
        return list(range(self.year_established + 1, self.current_year + 1))


class SchoolForum(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="forums")
    year = models.PositiveIntegerField(null=True, blank=True)
    name = models.CharField(max_length=255)
    is_general = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["year", "name"]
        unique_together = ("school", "year", "is_general")

    def __str__(self):
        return self.name


class SchoolMembership(models.Model):
    ROLE_CHOICES = [
        ("MEMBER", "Member"),
        ("CHAIRMAN", "Chairman"),
        ("SECRETARY", "Secretary"),
        ("PATRON", "Patron"),
        ("MODERATOR", "Moderator"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="school_memberships")
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="memberships")
    forum = models.ForeignKey(SchoolForum, on_delete=models.CASCADE, related_name="members")
    status = models.CharField(max_length=20, default="PENDING")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="MEMBER")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "forum")

    def __str__(self):
        return f"{self.user} -> {self.forum}"


class SchoolJoinRequest(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="school_join_requests")
    forum = models.ForeignKey(SchoolForum, on_delete=models.CASCADE, related_name="join_requests")
    graduation_year = models.PositiveIntegerField(null=True, blank=True)
    certificate = models.FileField(upload_to="school_join_certs/", null=True, blank=True)
    rejection_reason = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_school_join_requests")

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self):
        return f"{self.user} -> {self.forum} ({self.status})"


class SchoolForumMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    forum = models.ForeignKey(SchoolForum, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="school_forum_messages")
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Message by {self.sender} in {self.forum}"


class ForumRequest(models.Model):
    REQUEST_TYPE_CHOICES = [
        ("SCHOOL", "School Alumni"),
        ("ORGANIZATION", "Organization / Association"),
    ]
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("UNDER_REVIEW", "Under Review"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES, default="SCHOOL")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="forum_requests")
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_forum_requests")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    remarks = models.TextField(blank=True)

    school_name = models.CharField(max_length=255, blank=True)
    organization_name = models.CharField(max_length=255, blank=True)
    address = models.CharField(max_length=255, blank=True)
    lga = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True, default="Nigeria")
    phone = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    year_established = models.PositiveIntegerField(null=True, blank=True)
    school_type = models.CharField(max_length=40, blank=True)
    visibility = models.CharField(max_length=20, blank=True, default="PUBLIC")
    organization_type = models.CharField(max_length=40, blank=True)
    contact_person = models.CharField(max_length=255, blank=True)
    contact_position = models.CharField(max_length=255, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)
    join_policy = models.CharField(max_length=20, choices=[("OPEN", "Open"), ("CLOSED", "Closed")], default="CLOSED")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        if self.request_type == "SCHOOL":
            return f"School request: {self.school_name or 'Untitled'}"
        return f"Organization request: {self.organization_name or 'Untitled'}"


class IndependentForumRequest(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="independent_forum_requests")
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="requested_independent_forums")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    contact_name = models.CharField(max_length=255, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    objectives = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


class AdminRole(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="admin_role")
    is_super_admin = models.BooleanField(default=False)
    can_manage_schools = models.BooleanField(default=True)
    can_verify_users = models.BooleanField(default=True)
    can_manage_forums = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Admin role for {self.user}"
