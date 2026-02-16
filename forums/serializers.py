from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Forum, ForumMembership, ProfileRing, ForumJoinRequest, ForumInvitationCode,
    ForumPost, PostReaction, PostComment, PostCommentReply,
    Meeting, MeetingParticipant, MeetingMinute,
    ForumMeeting, MeetingAttendee,
    ForumPayment, ForumPaymentSubmission,
    Announcement, AnnouncementRecipient, AnnouncementRead,
    Poll, PollGroup, PollOption, PollVote,
    Notification, UserNotificationPreference
)

User = get_user_model()

class ForumSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    
    class Meta:
        model = Forum
        fields = [
            "id", "forum_id", "name", "description", "address", "email", "phone",
            "profile_picture", "slogan", "motto", "registration_details",
            "registration_certificate", "constitution", "objectives_rules",
            "logo", "is_completed", "is_verified", "is_searchable", "invitation_link",
            "created_by", "created_by_name", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "forum_id", "created_by", "created_by_name", "is_verified", "invitation_link", "created_at", "updated_at"]


class ForumCreateSerializer(serializers.ModelSerializer):
    """For creating a forum with minimal required fields"""
    class Meta:
        model = Forum
        fields = ["id", "name", "description", "address", "email", "phone", "profile_picture", "forum_id"]
        extra_kwargs = {
            "profile_picture": {"required": False},
            "forum_id": {"read_only": True},
        }

    def create(self, validated_data):
        import string
        import random
        
        # Generate unique forum_id (12 uppercase alphanumeric characters)
        while True:
            forum_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
            if not Forum.objects.filter(forum_id=forum_id).exists():
                break
        
        validated_data['forum_id'] = forum_id
        return super().create(validated_data)


class ForumCompleteSerializer(serializers.ModelSerializer):
    """For completing forum profile with additional fields"""
    class Meta:
        model = Forum
        fields = [
            "slogan", "motto", "registration_details",
            "registration_certificate", "constitution", "objectives_rules"
        ]

    def update(self, instance, validated_data):
        # Check if all required fields are present to mark as complete
        required_fields = ["slogan", "motto", "constitution"]
        for field in required_fields:
            if not getattr(instance, field):
                return super().update(instance, validated_data)
        
        # Mark as completed if all required fields are present
        instance.is_completed = all([
            getattr(instance, field, None) for field in required_fields
        ])
        return super().update(instance, validated_data)


class ForumJoinRequestSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)
    user_first_name = serializers.CharField(source="user.first_name", read_only=True)
    user_last_name = serializers.CharField(source="user.last_name", read_only=True)
    user_profile_photo = serializers.SerializerMethodField()
    forum_name = serializers.CharField(source="forum.name", read_only=True)
    forum_id = serializers.CharField(source="forum.forum_id", read_only=True)

    def get_user_profile_photo(self, obj):
        if hasattr(obj.user, 'profile') and obj.user.profile.photo:
            return obj.user.profile.photo.url
        return None

    class Meta:
        model = ForumJoinRequest
        fields = ["id", "user", "user_name", "user_first_name", "user_last_name", "user_profile_photo", "forum", "forum_id", "forum_name", "invitation_code", "status", "requested_at", "reviewed_at", "reviewed_by"]
        read_only_fields = ["id", "requested_at", "reviewed_at", "reviewed_by"]


class ForumInvitationCodeSerializer(serializers.ModelSerializer):
    forum_name = serializers.CharField(source="forum.name", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    can_be_used = serializers.SerializerMethodField()

    class Meta:
        model = ForumInvitationCode
        fields = [
            "id", "forum", "forum_name", "code", "usage_type", "max_usage_count",
            "current_usage_count", "valid_from", "valid_until", "created_by", "created_by_name",
            "is_active", "can_be_used", "created_at"
        ]
        read_only_fields = ["id", "forum", "code", "current_usage_count", "valid_from", "created_by", "created_at"]

    def get_can_be_used(self, obj):
        return obj.can_be_used()


class ForumMembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = ForumMembership
        fields = ["id", "forum", "role", "joined_at", "is_active"]


class ProfileRingSerializer(serializers.ModelSerializer):
    # Added read_only=True to prevent validation errors on write operations
    forum = serializers.CharField(source="membership.forum.name", read_only=True)

    class Meta:
        model = ProfileRing
        fields = ["forum", "ring_color", "updated_at"]


# ==================== POST SERIALIZERS ====================
class PostCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.get_full_name", read_only=True)
    author_profile = serializers.SerializerMethodField()
    author_id = serializers.CharField(source="author.id", read_only=True)
    replies_count = serializers.SerializerMethodField()

    class Meta:
        model = PostComment
        fields = ["id", "author", "author_name", "author_id", "author_profile", "content", "replies_count", "created_at", "updated_at"]
        read_only_fields = ["id", "author", "created_at", "updated_at"]

    def get_author_profile(self, obj):
        try:
            from accounts.models import Profile
            profile = Profile.objects.get(user=obj.author)
            return {
                "profile_photo": profile.profile_photo.url if profile.profile_photo else None,
                "phone": profile.phone,
                "gender": profile.gender,
            }
        except:
            return None

    def get_replies_count(self, obj):
        return obj.replies.count()


class PostCommentReplySerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.get_full_name", read_only=True)
    author_profile = serializers.SerializerMethodField()
    author_id = serializers.CharField(source="author.id", read_only=True)

    class Meta:
        model = PostCommentReply
        fields = ["id", "author", "author_name", "author_id", "author_profile", "content", "created_at", "updated_at"]
        read_only_fields = ["id", "author", "created_at", "updated_at"]

    def get_author_profile(self, obj):
        try:
            from accounts.models import Profile
            profile = Profile.objects.get(user=obj.author)
            return {
                "profile_photo": profile.profile_photo.url if profile.profile_photo else None,
                "phone": profile.phone,
                "gender": profile.gender,
            }
        except:
            return None


class PostReactionSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)

    class Meta:
        model = PostReaction
        fields = ["id", "reaction_type", "user", "user_name", "created_at"]
        read_only_fields = ["id", "user", "created_at"]


class ForumPostSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.get_full_name", read_only=True)
    reactions = PostReactionSerializer(many=True, read_only=True)
    comments = PostCommentSerializer(many=True, read_only=True)
    likes_count = serializers.SerializerMethodField()
    dislikes_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    user_reaction = serializers.SerializerMethodField()

    class Meta:
        model = ForumPost
        fields = [
            "id", "author", "author_name", "content", "image", "video",
            "is_pinned", "likes_count", "dislikes_count", "comments_count",
            "user_reaction", "reactions", "comments", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "author", "created_at", "updated_at", "reactions", "comments"]

    def get_likes_count(self, obj):
        return obj.reactions.filter(reaction_type="LIKE").count()

    def get_dislikes_count(self, obj):
        return obj.reactions.filter(reaction_type="DISLIKE").count()

    def get_comments_count(self, obj):
        return obj.comments.count()

    def get_user_reaction(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            reaction = obj.reactions.filter(user=request.user).first()
            return reaction.reaction_type if reaction else None
        return None


# ==================== MEETING SERIALIZERS ====================
class MeetingAttendeeSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)

    class Meta:
        model = MeetingAttendee
        fields = ["id", "user", "user_name", "joined_at"]
        read_only_fields = ["id", "joined_at"]


class ForumMeetingSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.get_full_name", read_only=True)
    attendees = MeetingAttendeeSerializer(many=True, read_only=True)
    attendees_count = serializers.SerializerMethodField()

    class Meta:
        model = ForumMeeting
        fields = [
            "id", "title", "description", "meeting_type", "venue",
            "scheduled_at", "is_live", "meeting_link", "minutes_pdf",
            "created_by", "created_by_name", "attendees", "attendees_count",
            "created_at"
        ]
        read_only_fields = ["id", "created_by", "created_at", "attendees"]

    def get_attendees_count(self, obj):
        return obj.attendees.count()


# ==================== PAYMENT SERIALIZERS ====================
class ForumPaymentSubmissionSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)

    class Meta:
        model = ForumPaymentSubmission
        fields = ["id", "user", "user_name", "amount_paid", "payment_date", "receipt_image"]
        read_only_fields = ["id", "payment_date"]


class ForumPaymentSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.get_full_name", read_only=True)
    submissions = ForumPaymentSubmissionSerializer(many=True, read_only=True)
    submissions_count = serializers.SerializerMethodField()
    user_status = serializers.SerializerMethodField()

    class Meta:
        model = ForumPayment
        fields = [
            "id", "payment_type", "name", "amount", "category", "due_date",
            "created_by", "created_by_name", "submissions", "submissions_count",
            "user_status", "created_at"
        ]
        read_only_fields = ["id", "created_by", "created_at", "submissions"]

    def get_submissions_count(self, obj):
        return obj.submissions.count()

    def get_user_status(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            submission = obj.submissions.filter(user=request.user).first()
            return "PAID" if submission else "PENDING"
        return "PENDING"


# ==================== ANNOUNCEMENT SERIALIZERS ====================
class AnnouncementReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnnouncementRead
        fields = ["user", "read_at"]
        read_only_fields = ["read_at"]


class AnnouncementSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.get_full_name", read_only=True)
    created_by_email = serializers.CharField(source="created_by.email", read_only=True)
    is_read = serializers.SerializerMethodField()
    read_count = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = [
            "id", "forum", "title", "message", "announcement_type", 
            "created_by", "created_by_name", "created_by_email",
            "created_at", "is_archived", "archived_at",
            "is_read", "read_count", "save_to_forum_feed"
        ]
        read_only_fields = ["id", "forum", "created_by", "created_by_name", "created_by_email", "created_at", "archived_at"]

    def get_is_read(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.reads.filter(user=request.user).exists()
        return False

    def get_read_count(self, obj):
        return obj.reads.count()


class AnnouncementRecipientSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)

    class Meta:
        model = AnnouncementRecipient
        fields = ["id", "user", "user_email", "user_name", "email_sent_at", "email_delivery_status", "email_error"]
        read_only_fields = ["id", "user_email", "user_name", "email_sent_at", "email_delivery_status", "email_error"]


# ==================== POLL SERIALIZERS ====================
class PollGroupSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.get_full_name", read_only=True)
    polls_count = serializers.SerializerMethodField()

    class Meta:
        model = PollGroup
        fields = [
            "id", "title", "description", "created_by", "created_by_name",
            "is_archived", "polls_count", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_by", "created_by_name", "created_at", "updated_at"]

    def get_polls_count(self, obj):
        return obj.polls.count()


class PollOptionSerializer(serializers.ModelSerializer):
    votes_count = serializers.SerializerMethodField()
    percentage = serializers.SerializerMethodField()
    voters = serializers.SerializerMethodField()

    class Meta:
        model = PollOption
        fields = ["id", "option_text", "votes_count", "percentage", "voters"]
        read_only_fields = ["id", "votes_count", "percentage", "voters"]

    def get_votes_count(self, obj):
        return obj.votes.count()

    def get_percentage(self, obj):
        poll = obj.poll
        total_votes = poll.votes.count()
        if total_votes == 0:
            return 0
        return round((obj.votes.count() / total_votes) * 100, 1)

    def get_voters(self, obj):
        """Return list of voters (only for OPEN ballot)"""
        context = self.context or {}
        request = context.get("request")
        poll = obj.poll
        
        # Only include voter info for OPEN ballots
        if poll.ballot_type != "OPEN":
            return []
        
        voters = []
        for vote in obj.votes.select_related("voter"):
            # Handle both Django User model and custom User model
            voter_user = vote.voter
            if hasattr(voter_user, 'get_full_name'):
                voter_name = voter_user.get_full_name() or voter_user.email
            elif hasattr(voter_user, 'first_name') and hasattr(voter_user, 'last_name'):
                voter_name = f"{voter_user.first_name} {voter_user.last_name}".strip() or voter_user.email
            else:
                voter_name = voter_user.email
            
            voters.append({
                "voter_name": voter_name,
                "voter_email": voter_user.email,
            })
        return voters


class PollSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    created_by_email = serializers.SerializerMethodField()
    group_title = serializers.SerializerMethodField()
    options = PollOptionSerializer(many=True, read_only=True)
    user_voted = serializers.SerializerMethodField()
    user_vote_count = serializers.SerializerMethodField()
    total_votes = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    winner = serializers.SerializerMethodField()
    result = serializers.SerializerMethodField()

    class Meta:
        model = Poll
        fields = [
            "id", "group", "group_title", "title", "description", "created_by", "created_by_name", "created_by_email",
            "created_at", "start_time", "end_time", 
            "ballot_type", "vote_type",
            "options", "user_voted", "user_vote_count", "total_votes",
            "status", "is_archived", "archived_at",
            "winner", "result",
            # Backward compatibility
            "question", "is_active", "ends_at"
        ]
        read_only_fields = [
            "id", "created_by", "created_at", "options", 
            "status", "winner", "result", "group_title"
        ]

    def get_created_by_name(self, obj):
        """Get creator's full name safely"""
        try:
            if obj.created_by:
                # Try get_full_name() for Django User model
                if hasattr(obj.created_by, 'get_full_name'):
                    return obj.created_by.get_full_name() or obj.created_by.email
                # Fallback for custom User model with first_name/last_name
                elif hasattr(obj.created_by, 'first_name') and hasattr(obj.created_by, 'last_name'):
                    full_name = f"{obj.created_by.first_name} {obj.created_by.last_name}".strip()
                    return full_name or obj.created_by.email
                else:
                    return obj.created_by.email
            return "Unknown"
        except:
            return obj.created_by.email if obj.created_by else "Unknown"

    def get_created_by_email(self, obj):
        """Get creator's email safely"""
        return obj.created_by.email if obj.created_by else ""

    def get_group_title(self, obj):
        """Return group title if poll belongs to a group"""
        try:
            return obj.group.title if obj.group else None
        except:
            return None

    def get_user_voted(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.votes.filter(voter=request.user).exists()
        return False

    def get_user_vote_count(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.votes.filter(voter=request.user).count()
        return 0

    def get_total_votes(self, obj):
        return obj.votes.count()

    def get_status(self, obj):
        try:
            return obj.status
        except:
            return "CLOSED"

    def get_winner(self, obj):
        """Calculate winner based on majority logic"""
        try:
            total_votes = obj.votes.count()
            if total_votes == 0:
                return None
            
            # Find option with most votes
            option_votes = {}
            for option in obj.options.all():
                votes = option.votes.count()
                option_votes[option.id] = {"name": option.option_text or option.text, "votes": votes}
            
            if not option_votes:
                return None
            
            max_votes = max(v["votes"] for v in option_votes.values())
            winners = [v["name"] for v in option_votes.values() if v["votes"] == max_votes]
            
            if len(winners) > 1:
                return None  # Tie detected
            
            return winners[0] if winners else None
        except Exception as e:
            print(f"Error calculating winner: {str(e)}")
            return None

    def get_result(self, obj):
        """Return result message: Winner or Tie"""
        try:
            total_votes = obj.votes.count()
            if total_votes == 0:
                return "No votes yet"
            
            # Find option with most votes
            option_votes = {}
            for option in obj.options.all():
                votes = option.votes.count()
                option_votes[option.id] = {"name": option.option_text or option.text, "votes": votes}
            
            if not option_votes:
                return "No options found"
            
            max_votes = max(v["votes"] for v in option_votes.values())
            winners = [v["name"] for v in option_votes.values() if v["votes"] == max_votes]
            
            if len(winners) > 1:
                return "Result: Tie"
            
            return f"Winner: {winners[0]}" if winners else "No winner"
        except Exception as e:
            print(f"Error calculating result: {str(e)}")
            return "Unable to calculate result"
        for option in obj.options.all():
            votes = option.votes.count()
            if votes > 0:
                option_votes[option.id] = {"name": option.option_text, "votes": votes}
        
        if not option_votes:
            return "No votes yet"
        
        max_votes = max(v["votes"] for v in option_votes.values())
        winners = [v["name"] for v in option_votes.values() if v["votes"] == max_votes]
        
        if len(winners) > 1:
            return "Result: Tie"
        elif winners:
            return f"Winner: {winners[0]}"
        
        return "No winner"


# ==================== MEETING SERIALIZERS ====================
class MeetingParticipantSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    user_profile = serializers.SerializerMethodField()

    class Meta:
        model = MeetingParticipant
        fields = [
            "id", "user", "user_email", "user_name", "user_profile",
            "joined_at", "left_at", "duration_seconds", "is_currently_active", "last_heartbeat",
            "is_marked_present", "presence_percentage"
        ]
        read_only_fields = ["id", "joined_at", "left_at", "duration_seconds", "last_heartbeat", "is_marked_present", "presence_percentage"]

    def get_user_profile(self, obj):
        try:
            from accounts.models import Profile
            profile = Profile.objects.get(user=obj.user)
            return {
                "profile_photo": profile.profile_photo.url if profile.profile_photo else None,
                "phone": profile.phone,
                "gender": profile.gender,
            }
        except:
            return None


class MeetingMinuteSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source="uploaded_by.get_full_name", read_only=True)
    pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = MeetingMinute
        fields = ["id", "meeting", "pdf_file", "pdf_url", "uploaded_at", "uploaded_by", "uploaded_by_name"]
        read_only_fields = ["id", "meeting", "uploaded_at", "uploaded_by"]

    def get_pdf_url(self, obj):
        if obj.pdf_file:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.pdf_file.url)
            return obj.pdf_file.url
        return None


class MeetingCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating meetings (admin only)"""
    allowed_participant_ids = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        many=True,
        write_only=True,
        required=False,
        source="allowed_participants"
    )
    
    class Meta:
        model = Meeting
        fields = [
            "title", "description", "meeting_type", "venue",
            "scheduled_start", "scheduled_end", "is_all_members_allowed",
            "allowed_participant_ids"
        ]

    def validate(self, data):
        from django.utils import timezone
        
        if data["scheduled_start"] >= data["scheduled_end"]:
            raise serializers.ValidationError("Start time must be before end time")
        
        if data["meeting_type"] == "PHYSICAL" and not data.get("venue"):
            raise serializers.ValidationError("Venue is required for physical meetings")
        
        # Validate start time is in the future (at least 15 minutes)
        now = timezone.now()
        min_future_time = now.replace(second=0, microsecond=0) + timezone.timedelta(minutes=15)
        if data["scheduled_start"] < min_future_time:
            raise serializers.ValidationError("Meeting must be at least 15 minutes in the future")
        
        return data

    def create(self, validated_data):
        import uuid
        request = self.context.get("request")
        forum_id = self.context.get("forum_id")
        
        allowed_participants = validated_data.pop("allowed_participants", [])
        is_all_members_allowed = validated_data.get("is_all_members_allowed", True)
        
        # Generate unique room ID
        room_id = f"room_{uuid.uuid4().hex[:12]}"
        
        meeting = Meeting.objects.create(
            forum_id=forum_id,
            created_by=request.user,
            room_id=room_id,
            **validated_data
        )
        
        # Set allowed participants if specified
        if allowed_participants:
            meeting.allowed_participants.set(allowed_participants)
            meeting.is_all_members_allowed = False
            meeting.save()
        
        return meeting
        return meeting


class MeetingDetailSerializer(serializers.ModelSerializer):
    """Detailed meeting serializer with participants and status"""
    created_by_name = serializers.CharField(source="created_by.get_full_name", read_only=True)
    created_at_display = serializers.SerializerMethodField()
    allowed_participants_data = MeetingParticipantSerializer(
        source="allowed_participants", 
        many=True, 
        read_only=True
    )
    participants = MeetingParticipantSerializer(many=True, read_only=True)
    minute = MeetingMinuteSerializer(read_only=True)
    participant_count = serializers.SerializerMethodField()
    current_end_time = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_upload_minutes = serializers.SerializerMethodField()
    can_extend_meeting = serializers.SerializerMethodField()
    is_user_allowed = serializers.SerializerMethodField()
    attended_count = serializers.SerializerMethodField()

    class Meta:
        model = Meeting
        fields = [
            "id", "forum", "title", "description", "meeting_type", "venue",
            "scheduled_start", "scheduled_end", "actual_end", "current_end_time",
            "room_id", "status", "is_live", "is_cancelled", "cancelled_reason",
            "created_by", "created_by_name", "created_at", "created_at_display",
            "is_all_members_allowed", "allowed_participants_data",
            "participants", "participant_count", "attended_count",
            "minute", "minutes_pdf", "minutes_uploaded_at",
            "can_edit", "can_upload_minutes", "can_extend_meeting", "is_user_allowed",
            "updated_at"
        ]
        read_only_fields = [
            "id", "forum", "room_id", "created_by", "is_live",
            "minutes_uploaded_at", "created_at", "created_at_display", "updated_at"
        ]

    def get_created_at_display(self, obj):
        """Format created_at as readable datetime"""
        if obj.created_at:
            return obj.created_at.strftime("%B %d, %Y at %I:%M %p")
        return None

    def get_current_end_time(self, obj):
        """Returns actual_end if extended, else scheduled_end"""
        end_time = obj.get_current_end_time()
        return end_time.isoformat() if end_time else None

    def get_participant_count(self, obj):
        return obj.participants.filter(is_currently_active=True).count()
    
    def get_attended_count(self, obj):
        """Count participants who are marked present"""
        return obj.participants.filter(is_marked_present=True).count()

    def get_status(self, obj):
        return obj.status

    def get_can_edit(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        
        # Check if user is forum admin
        try:
            from .models import ForumMembership
            membership = ForumMembership.objects.get(
                user=request.user,
                forum=obj.forum,
                is_active=True
            )
            return membership.role in ["SA", "CP"]  # Sole Admin or Chairperson
        except:
            return False
    
    def get_can_extend_meeting(self, obj):
        """Admin can extend only if meeting is currently live"""
        if not self.get_can_edit(obj):
            return False
        return obj.status == "LIVE"
    
    def get_can_upload_minutes(self, obj):
        return self.get_can_edit(obj)
    
    def get_is_user_allowed(self, obj):
        """Check if user is allowed to join this meeting"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        
        # Check forum membership first
        try:
            from .models import ForumMembership
            ForumMembership.objects.get(
                user=request.user,
                forum=obj.forum,
                is_active=True
            )
        except:
            return False
        
        # If all members allowed, user can join
        if obj.is_all_members_allowed:
            return True
        
        # Otherwise check if user is in allowed_participants
        return obj.allowed_participants.filter(id=request.user.id).exists()

    def get_can_upload_minutes(self, obj):
        return self.get_can_edit(obj)


class MeetingListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for meeting lists"""
    created_by_name = serializers.CharField(source="created_by.get_full_name", read_only=True)
    participant_count = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Meeting
        fields = [
            "id", "forum", "title", "meeting_type", "venue",
            "scheduled_start", "scheduled_end", "status",
            "is_live", "created_by", "created_by_name",
            "participant_count", "created_at"
        ]
        read_only_fields = fields

    def get_participant_count(self, obj):
        return obj.participants.filter(is_currently_active=True).count()

    def get_status(self, obj):
        return obj.status


# ==================== NOTIFICATION SERIALIZERS ====================

class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for user notifications"""
    forum_name = serializers.CharField(source="forum.name", read_only=True)
    notification_type_display = serializers.CharField(source="get_notification_type_display", read_only=True)
    tab_display = serializers.CharField(source="get_tab_display", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id", "user", "forum", "forum_name", "notification_type",
            "notification_type_display", "title", "message", "tab",
            "tab_display", "object_id", "is_read", "created_at"
        ]
        read_only_fields = ["id", "user", "forum", "created_at"]


class NotificationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for notification lists"""
    forum_name = serializers.CharField(source="forum.name", read_only=True)
    notification_type_display = serializers.CharField(source="get_notification_type_display", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id", "forum", "forum_name", "notification_type",
            "notification_type_display", "title", "message", "tab",
            "is_read", "created_at"
        ]
        read_only_fields = fields


class UserNotificationPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for user notification preferences"""
    
    class Meta:
        model = UserNotificationPreference
        fields = [
            "id", "user",
            # Feed settings
            "feed_in_app", "feed_push", "feed_email",
            # Meetings
            "meetings_in_app", "meetings_push", "meetings_email",
            # Payments
            "payments_in_app", "payments_push", "payments_email",
            # Disbursements
            "disbursements_in_app", "disbursements_push", "disbursements_email",
            # Members
            "members_in_app", "members_push", "members_email",
            # Forum info
            "forum_info_in_app", "forum_info_push", "forum_info_email",
            # Announcements
            "announcements_in_app", "announcements_push", "announcements_email",
            # Polls
            "polls_in_app", "polls_push", "polls_email",
            # Metadata
            "created_at", "updated_at"
        ]
        read_only_fields = ["id", "user", "created_at", "updated_at"]