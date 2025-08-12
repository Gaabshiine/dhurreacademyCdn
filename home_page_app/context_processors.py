from django.conf import settings
import os
from datetime import datetime
from django.utils.timesince import timesince
from admin_page_app.models import FAQ, Course, Review, Enrollment, Certificate, Category, Payment, Event, ContactInfo
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import (
    Count, Q, Avg, Exists, OuterRef, F, Prefetch, Subquery, Case, When, Value, BooleanField
)
from django.db.models.functions import Coalesce
from account_app.models import Instructor, Student, Profile, CustomUser
from django.utils import timezone

import logging

logger = logging.getLogger(__name__)

# 1.1) Define a context processor to fetch course data
def course_context_processor(request):
    student_user = request.user if request.user.is_authenticated else None

    try:
        # Base query for all courses
        courses = Course.objects.select_related('category', 'instructor') \
            .annotate(
                instructor_first_name=F('instructor__first_name'),
                instructor_last_name=F('instructor__last_name'),
                category_name=F('category__name'),
                category_is_free=F('category__is_free')
            ).all()

        # If student is logged in, annotate with enrollment status
        if student_user:
            courses = courses.annotate(
                is_enrolled=Exists(
                    Enrollment.objects.filter(course_id=OuterRef('pk'), student=student_user)
                )
            )
        else:
            for course in courses:
                course.is_enrolled = False  # Default value for non-authenticated users

        # Add image processing and ratings
        for course in courses:
            # Handle image URLs
            if course.image:
                course.image_url = os.path.join(settings.MEDIA_URL, course.image.name).replace('\\', '/')
            else:
                course.image_url = os.path.join(settings.STATIC_URL, 'home_page_app/images/courses-1.jpg')

            # Fetch average rating for the course
            rating_data = Review.objects.filter(course_id=course.id).aggregate(
                average_rating=Avg('rating'),
                rating_count=Count('rating')
            )

            if rating_data['average_rating']:
                average_rating = rating_data['average_rating']
                course.rating_display = "{:.1f}".format(average_rating)
                course.rating_width = (average_rating / 5) * 100
            else:
                course.rating_display = "0.0"
                course.rating_width = 0

            course.rating_count = rating_data['rating_count']

        # Separate free and premium courses
        free_courses = [course for course in courses if course.category_is_free]
        premium_courses = [course for course in courses if not course.category_is_free]

        all_courses_count = len(courses)

        return {
            'all_courses': courses,
            'free_courses': free_courses,
            'premium_courses': premium_courses,
            'all_courses_count': all_courses_count,
        }

    except ObjectDoesNotExist as e:
        print(f"ObjectDoesNotExist: {e}")
        return {}
    except Exception as e:
        print(f"An error occurred: {e}")
        return {}

# 1.2) Define a context processor to fetch category data
def category_context_processor(request):
    try:
        categories_queryset = Category.objects.prefetch_related(
            Prefetch(
                'course_set', 
                queryset=Course.objects.all(),
                to_attr='courses'  
            )
        ).all().order_by('name')

        categories_dict = {}
        for category in categories_queryset:
            courses_data = [
                {
                    'id': course.id,
                    'name': course.name,
                    'category_is_free': category.is_free
                }
                for course in category.courses
            ]
            image_url = os.path.join(settings.MEDIA_URL, category.image.name) if category.image else os.path.join(settings.STATIC_URL, 'home_page_app/images/default-category.jpg')

            categories_dict[category.id] = {
                'id': category.id,
                'name': category.name,
                'image': category.image,
                'image_url': image_url,
                'courses': courses_data,
            }

        categories_list = list(categories_dict.values())

        return {
            'all_categories': categories_list,
        }

    except Exception as e:
        print(f"An error occurred while fetching categories: {e}")
        return {'all_categories': []}


# 1.3) Define a context processor to fetch instructor data
def instructors_context_processor(request):
    student_user = request.user if request.user.is_authenticated else None

    try:
        # Check if the student is enrolled in any course taught by the instructor
        enrollment_check_subquery = Enrollment.objects.filter(
            course__instructor_id=OuterRef('pk'),
            student_id=student_user.id if student_user else None
        ).values('id')[:1]

        # Now we filter instructors based on the user_type using the CustomUser model
        instructors = Instructor.objects.annotate(
            profile_picture=Subquery(
                Profile.objects.filter(user=OuterRef('user'), user__user_type='instructor')
                .values('profile_picture')[:1]
            ),
            bio=Subquery(
                Profile.objects.filter(user=OuterRef('user'), user__user_type='instructor')
                .values('bio')[:1]
            ),
            total_courses=Count('user__course', distinct=True),
            total_students=Count('user__course__enrollment__student', distinct=True),
            average_rating=Avg('user__course__review__rating'),
            is_enrolled_instructor=Case(
                When(Exists(enrollment_check_subquery), then=Value(True)),
                default=Value(False),
                output_field=BooleanField()
            )
        ).filter(user__user_type='instructor').distinct()  # Ensure filtering is done via CustomUser

        instructors_data = []
        for instructor in instructors:
            # Handle profile pictures
            image_url = os.path.join(settings.MEDIA_URL, instructor.profile_picture) if instructor.profile_picture else os.path.join(settings.STATIC_URL, 'home_page_app/images/avatar-placeholder.jpg')
            average_rating = instructor.average_rating or 0
            average_rating = min(average_rating, 5)

            full_stars = range(int(average_rating))
            half_star = average_rating % 1 >= 0.5
            empty_stars = range(5 - int(average_rating) - int(half_star))

            instructors_data.append({
                'id': instructor.id,
                'first_name': instructor.user.first_name,
                'last_name': instructor.user.last_name,
                'department': instructor.department,
                'bio': instructor.bio,
                'profile_picture': instructor.profile_picture,
                'image_url': image_url,
                'average_rating': average_rating,
                'full_stars': full_stars,
                'half_star': half_star,
                'empty_stars': empty_stars,
                'total_courses': instructor.total_courses,
                'total_students': instructor.total_students,
                'is_enrolled_instructor': instructor.is_enrolled_instructor,
            })

        return {
            'instructors': instructors_data,
            'instructor_counts': len(instructors_data),
        }
    except Exception as e:
        print(f"Error fetching instructors: {e}")
        return {'instructors': [], 'instructor_counts': 0}
    

# 1.4) Define a context processor to fetch instructor rating data
def instructor_rating_display(request):
    course_id = request.resolver_match.kwargs.get('course_id')
    if not course_id:
        return {}

    try:
        instructor_course = Course.objects.filter(id=course_id).select_related('instructor').first()
        if not instructor_course or not instructor_course.instructor:
            return {}

        instructor = instructor_course.instructor
        instructor_rating = Review.objects.filter(course__instructor_id=instructor.id).aggregate(average_rating=Avg('rating'))

        if instructor_rating['average_rating']:
            average_rating = round(instructor_rating['average_rating'], 1)
            rating_width = (average_rating / 5) * 100
        else:
            average_rating = "No ratings yet"
            rating_width = 0

    except Exception as e:
        print(f"Error calculating instructor rating: {e}")
        average_rating = "Error calculating rating"
        rating_width = 0

    return {
        'instructor': instructor,
        'average_rating': average_rating,
        'rating_width': rating_width
    }


# 1.5) Define a context processor to fetch certificates data
def certificates_context_processor(request):
    student_user = request.user if request.user.is_authenticated else None
    if not student_user:
        return {'certificates': []}

    try:
        certificates = Certificate.objects.filter(student_id=student_user.id).select_related('course').values(
            'id', 'issue_date', 'course__name', 'course__id'
        )

        certificate_list = []
        for certificate in certificates:
            course_id = certificate['course__id']  
            certificate_filename = f"certificate_{student_user.id}_{course_id}.pdf"
            certificate_path = os.path.join(settings.MEDIA_ROOT, 'certificate', certificate_filename)

            # 🔹 Correct way to form media URLs
            certificate_url = f"{settings.MEDIA_URL}certificate/{certificate_filename}"

            # ✅ Ensure the certificate file actually exists
            if os.path.exists(certificate_path):
                download_url = certificate_url  # Use MEDIA_URL-based path
            else:
                download_url = None  

            certificate_data = {
                'id': certificate['id'],
                'course_name': certificate['course__name'],
                'title': f"Certificate for {certificate['course__name']}",
                'issue_date': certificate['issue_date'].strftime('%B %d, %Y'),
                'download_url': download_url,
            }
            certificate_list.append(certificate_data)

        return {'certificates': certificate_list}

    except Exception as e:
        print(f"Error fetching certificates: {e}")
        return {'certificates': []}

# 1.6) Define a context processor to fetch reviews data
def reviews_context_processor(request):
    student_user = request.user if request.user.is_authenticated else None

    try:
        # Ensure student_user is not None before using student_user.id
        student_id = student_user.id if student_user else None

        profile_picture_subquery = Profile.objects.filter(
            user=OuterRef('student'),
            user__user_type='student'
        ).values('profile_picture')[:1]

        reviews = (
            Review.objects
            .select_related('course', 'student')
            .annotate(
                course_name=F('course__name'),
                course_image=F('course__image'),
                student_first_name=F('student__first_name'),
                student_middle_name=F('student__middle_name'),
                student_last_name=F('student__last_name'),
                student_profile_picture=Coalesce(Subquery(profile_picture_subquery), Value(None)),
                is_student_review=Case(
                    When(student_id=student_id, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField()
                )
            )
            .filter(student__user_type='student')  # Ensure filtering is done via CustomUser
            .order_by('-created_at')
        )

        reviews_list = []
        for review in reviews:
            student_profile_picture = f"/media/{review.student_profile_picture}" if review.student_profile_picture else '/static/home_page_app/images/avatar-placeholder.jpg'
            course_image_url = f"/media/{review.course_image}" if review.course_image else '/static/home_page_app/images/courses/courses-8.jpg'

            reviews_list.append({
                'id': review.id,
                'review_text': review.review_text,
                'rating': review.rating,
                'created_at': review.created_at,
                'time_ago': timesince(review.created_at, now=timezone.now()) + ' ago',
                'course_name': review.course_name,
                'course_image_url': course_image_url,
                'student_profile_image_url': student_profile_picture,
                'is_student_review': review.is_student_review,
                'student_name': f"{review.student_first_name} {review.student_middle_name}",
            })

    except Exception as e:
        print(f"Error fetching reviews: {e}")
        reviews_list = []

    return {
        'reviews': reviews_list,
    }


# 1.7) Define a context processor to fetch payments data
def payments_context_processor(request):
    student_user = request.user if request.user.is_authenticated else None
    
    if not student_user:
        return {'purchases': []}

    try:
        payments = Payment.objects.filter(student_id=student_user.id).select_related('course').annotate(
            course_name=F('course__name'),
            course_image=F('course__image')
        )

        purchases = []
        for payment in payments:
            if payment.course_image:
                course_image_url = f'/media/{payment.course_image}'
            else:
                course_image_url = '/static/home_page_app/images/courses/courses-8.jpg'

            purchases.append({
                'id': payment.id,
                'total_amount': payment.total_amount,
                'status': payment.status,
                'payment_date': payment.payment_date,
                'course_name': payment.course_name,
                'course_image_url': course_image_url
            })

    except Exception as e:
        print(f"Error fetching payments: {e}")
        purchases = []

    return {
        'purchases': purchases,
    }


# 1.8) Define a context processor to fetch FAQ data
def faq_context_processor(request):
    try:
        faqs = FAQ.objects.all().order_by('-created_at')
        for faq in faqs:
            if faq.video_url:
                faq.video_url = faq.video_url.replace('autoplay=true', 'autoplay=false')
    except ObjectDoesNotExist as e:
        print(f"ObjectDoesNotExist: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

    return {
        'faqs': faqs,
    }


# 1.9) Define a context processor to fetch event data
def event_context_processor(request):
    try:
        latest_event = Event.objects.order_by('-event_date').first()
        if not latest_event:
            latest_event = None
    except Exception as e:
        print(f"Error fetching the latest event: {e}")
        latest_event = None

    return {
        'latest_event': latest_event,
    }


# 1.10) Define a context processor to fetch contact info
def home_page_context_processor(request):
    try:
        contact = ContactInfo.objects.first()
    except Exception as e:
        print(f"Error fetching contact info: {e}")
        contact = None

    # Ensure contact is always available with default values
    return {
        'contact': {
            'phone_number': contact.phone_number if contact else "N/A",
            'address': contact.address if contact else "N/A",
            'email': contact.email if contact else "N/A",
        }
    }
















