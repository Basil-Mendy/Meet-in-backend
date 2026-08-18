from django.db import migrations, models


def forward_migrate_school_forums(apps, schema_editor):
    import random
    import string
    from django.db import transaction

    Forum = apps.get_model("forums", "Forum")
    School = apps.get_model("alumni", "School")
    SchoolForum = apps.get_model("alumni", "SchoolForum")
    SchoolMembership = apps.get_model("alumni", "SchoolMembership")
    ForumMembership = apps.get_model("forums", "ForumMembership")

    def gen_forum_id():
        while True:
            val = "".join(random.choices(string.ascii_uppercase + string.digits, k=12))
            if not Forum.objects.filter(forum_id=val).exists():
                return val

    mapping = {}

    with transaction.atomic():
        for sf in SchoolForum.objects.select_related("school").all():
            school = sf.school
            forum_id = gen_forum_id()
            forum_vals = {
                "forum_id": forum_id,
                "name": sf.name,
                "description": sf.description or "",
                "address": school.address or "",
                "state": school.state or "",
                "lga": school.lga or "",
                "country": school.country or "Nigeria",
                "is_completed": True,
                "is_verified": True,
                "is_searchable": not bool(sf.is_general),
                "created_by_id": getattr(school, "created_by_id", None) or None,
                "forum_type": "SCHOOL_CLASS",
                "school_id": school.id,
                "graduation_year": sf.year,
                "nickname": "",
                "is_general": bool(sf.is_general),
            }

            # Remove keys with None for created_by to avoid integrity errors
            if forum_vals["created_by_id"] is None:
                # pick a site admin user if available; otherwise skip created_by and rely on DB default (may fail if non-null)
                del forum_vals["created_by_id"]

            new_forum = Forum.objects.create(**forum_vals)
            mapping[sf.id] = new_forum.id

        # Migrate school memberships to forum memberships
        role_map = {"CHAIRMAN": "P", "SECRETARY": "SEC", "MODERATOR": "MOD1"}
        for sm in SchoolMembership.objects.select_related("forum", "user").all():
            sf = sm.forum
            new_forum_id = mapping.get(sf.id)
            if not new_forum_id:
                continue
            defaults = {"forum_id": new_forum_id, "user_id": sm.user_id}
            role = role_map.get(sm.role, "MEMBER")
            ForumMembership.objects.get_or_create(user_id=sm.user_id, forum_id=new_forum_id, defaults={"role": role, "is_active": sm.status == "APPROVED"})


def backward_remove_migrated_forums(apps, schema_editor):
    Forum = apps.get_model("forums", "Forum")
    # Only remove forums we marked as SCHOOL_CLASS during forward migration
    Forum.objects.filter(forum_type="SCHOOL_CLASS").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("forums", "0022_forum_verification_expires_at_and_more"),
        ("alumni", "0009_forumrequest"),
    ]

    operations = [
        migrations.AddField(
            model_name="forum",
            name="forum_type",
            field=models.CharField(choices=[("SCHOOL_CLASS", "School Alumni Class Forum"), ("ORGANIZATION", "Organization Forum")], default="ORGANIZATION", max_length=20),
        ),
        migrations.AddField(
            model_name="forum",
            name="school",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name="class_forums", to="alumni.School"),
        ),
        migrations.AddField(
            model_name="forum",
            name="graduation_year",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="forum",
            name="nickname",
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name="forum",
            name="is_general",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(forward_migrate_school_forums, backward_remove_migrated_forums),
    ]
