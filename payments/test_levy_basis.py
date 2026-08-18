from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from accounts.models import Profile
from forums.models import Forum
from .models import ForumPayment, PaymentCategory
from .serializers import ForumPaymentSerializer


User = get_user_model()


class LevyBasisSelectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='member@example.com',
            password='secret123',
            first_name='Jane',
            last_name='Doe',
            phone='08000000001',
        )
        self.profile, _ = Profile.objects.get_or_create(user=self.user)
        self.profile.gender = 'female'
        self.profile.date_of_birth = '2000-01-01'
        self.profile.save()

        self.forum = Forum.objects.create(
            name='Test Forum',
            description='Test',
            forum_type='ORGANIZATION',
            town='Lagos',
            country='Nigeria',
            email='forum@example.com',
            phone='08000000000',
            created_by=self.user,
        )

    def test_gender_levy_uses_gender_categories_only(self):
        payment = ForumPayment.objects.create(
            forum=self.forum,
            title='Female Levy',
            type='LEVY',
            levy_basis='GENDER',
            created_by=self.user,
        )
        PaymentCategory.objects.create(payment=payment, category='female', amount=Decimal('200.00'))
        PaymentCategory.objects.create(payment=payment, category='male', amount=Decimal('100.00'))

        amount = payment.member_amount_for(self.user)
        self.assertEqual(amount, Decimal('200.00'))

    def test_age_levy_uses_age_categories_only(self):
        payment = ForumPayment.objects.create(
            forum=self.forum,
            title='Age Levy',
            type='LEVY',
            levy_basis='AGE',
            created_by=self.user,
        )
        PaymentCategory.objects.create(payment=payment, category='age_18_plus', amount=Decimal('300.00'))
        PaymentCategory.objects.create(payment=payment, category='below_18', amount=Decimal('150.00'))

        amount = payment.member_amount_for(self.user)
        self.assertEqual(amount, Decimal('300.00'))

    def test_serializer_persists_levy_category_amounts(self):
        serializer = ForumPaymentSerializer(data={
            'title': 'Gender Levy',
            'type': 'LEVY',
            'levy_basis': 'GENDER',
            'categories': [
                {'category': 'male', 'amount': '100.00', 'is_active': True},
                {'category': 'female', 'amount': '500.00', 'is_active': True},
            ],
        })

        self.assertTrue(serializer.is_valid(), serializer.errors)
        payment = serializer.save(forum=self.forum, created_by=self.user)

        male_amount = payment.categories.get(category='male').amount
        female_amount = payment.categories.get(category='female').amount

        self.assertEqual(str(male_amount), '100.00')
        self.assertEqual(str(female_amount), '500.00')
