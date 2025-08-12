from django.shortcuts import render
from django.http import JsonResponse
from django.core.mail import send_mail
from django.utils import timezone
from django.urls import reverse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

from django.utils.timezone import now
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from PyPDF2 import PdfReader, PdfWriter
import os
import io

from admin_page_app.models import Course, ContactInfo, Enrollment, Payment, Lesson, LessonCompletion, Review, Certificate, Event, Category
from account_app.models import Student, Instructor, Profile, CustomUser
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, F, Avg, Q, Subquery, OuterRef

from django.core.paginator import Paginator
from datetime import date, timedelta

from home_page_app.utils import extract_youtube_id







# Create your views here.

# -------------------------------------------------------> 1) Start: Public views <-------------------------------------------------------

# 1.1) home page view
def home_view(request):
    return render(request, 'home_page_app/index.html')

# 1.2) about page view
def about_view(request):
    return render(request, "home_page_app/about.html")

# 1.3) contact page view
def contact_view(request):
    # Fetch the contact info from the database (ensure it's not None)
    contact_info = ContactInfo.objects.first()

    if not contact_info:
        contact_info = {
            'address': "N/A",
            'phone_number': "N/A",
            'email': "N/A",
            'secondary_email': "N/A",
            'map_embed_url': "",
        }

    if request.method == "POST":
        name = request.POST.get('name')
        email = request.POST.get('email')
        message = request.POST.get('message')

        if not name or not email or not message:
            return JsonResponse({'success': False})

        try:
            send_mail(
                subject=f"New Contact Form Submission from {name}",
                message=message,
                from_email=email,
                recipient_list=['mohaaibraahim584@gmail.com'],
                fail_silently=False,
            )
            return JsonResponse({'success': True})
        except Exception as e:
            print(f"Error sending email: {e}")
            return JsonResponse({'success': False})

    return render(request, "home_page_app/contact.html", {"contact_info": contact_info})

# 1.4) search results view
def search_results_view(request):
    """
    Handles search functionality across courses, categories, and lessons.
    """
    query = request.GET.get('q', '').strip()

    if not query:
        return render(request, 'home_page_app/search_results.html', {'results': [], 'query': ''})

    try:
        # Search across Course names, Category names, and Lesson titles
        search_results = (
            Course.objects.filter(
                Q(name__icontains=query) |
                Q(category__name__icontains=query) |
                Q(lesson__title__icontains=query)  # Ensure Course has a relation to Lesson
            )
            .annotate(
                average_rating=Avg('review__rating'),
                rating_count=Count('review__id')
            )
            .select_related('category')
            .prefetch_related('lesson_set')
        )

        results = []
        for course in search_results:
            result = {
                'id': course.id,
                'course_name': course.name,
                'description': course.description,
                'price': course.course_amount,
                'category_name': course.category.name,
                'average_rating': round(course.average_rating or 0, 1),
                'rating_count': course.rating_count or 0,
                'image_url': f"/media/{course.image}" if course.image else '/static/home_page_app/images/courses-1.jpg'
            }
            results.append(result)

    except Exception as e:
        print(f"Error in search results view: {e}")
        results = []

    return render(request, 'home_page_app/search_results.html', {'results': results, 'query': query})

# -------------------------------------------------------> 1) End: Public views <-------------------------------------------------------



# -------------------------------------------------------> 2) Start: Student and Instructor Dashboard <-------------------------------------------------------

# 2.1) student dashboard view
@login_required(login_url='/student/login/')
def student_dashboard(request):
    """
    View for the student dashboard. Retrieves student-related data using request.user.
    """

    # Ensure request.user is a CustomUser instance and is a student
    if not isinstance(request.user, CustomUser) or request.user.user_type != 'student':
        return redirect('home_page_app:home')  # Redirect if not a student

    try:
        # Fetch the Student instance linked to the logged-in user
        student = get_object_or_404(Student, user=request.user)

        # Fetch enrolled courses count
        enrolled_courses = Enrollment.objects.filter(student=student.user).count()

        # Fetch active courses (where student hasn't completed all lessons)
        active_courses = Enrollment.objects.filter(student=student.user).annotate(
            total_lessons=Count('course__lesson', distinct=True),
            completed_lessons=Count('course__lesson__lessoncompletion', filter=Q(course__lesson__lessoncompletion__student=student.user), distinct=True)
        ).filter(total_lessons__gt=F('completed_lessons')).count()

        # Fetch completed courses (where all lessons are completed)
        completed_courses = Enrollment.objects.filter(student=student.user).annotate(
            total_lessons=Count('course__lesson', distinct=True),
            completed_lessons=Count('course__lesson__lessoncompletion', filter=Q(course__lesson__lessoncompletion__student=student.user), distinct=True)
        ).filter(total_lessons=F('completed_lessons')).count()

        # Fetch total students in the system
        total_students = Student.objects.count()

        # Fetch total courses in the system
        total_courses = Course.objects.count()

        # Fetch total earnings (approved payments)
        total_earnings = Payment.objects.filter(student=student.user, status='approved').aggregate(
            total_earnings=Sum('total_amount')
        )['total_earnings'] or 0

    except Exception as e:
        import traceback
        print(f"Error fetching student dashboard data: {e}")
        traceback.print_exc()
        enrolled_courses = active_courses = completed_courses = total_students = total_courses = total_earnings = 0

    # Pass the same context variables as before
    context = {
        'enrolled_courses': enrolled_courses,
        'active_courses': active_courses,
        'completed_courses': completed_courses,
        'total_students': total_students,
        'total_courses': total_courses,
        'total_earnings': total_earnings,
    }

    return render(request, 'home_page_app/dashboard.html', context)

@login_required(login_url='/student/login/')
def instructor_dashboard(request):
    """
    View for the instructor dashboard. Retrieves instructor-related data.
    """
    if request.user.user_type != 'instructor':
        return redirect('home_page_app:home')  # Redirect if not an instructor

    try:
        instructor = get_object_or_404(Instructor, user=request.user)

        # Fetch instructor profile
        profile = Profile.objects.filter(user=instructor.user).first()
        profile_picture_url = profile.profile_picture.url if profile and profile.profile_picture else '/static/home_page_app/images/avatar-placeholder.jpg'

        # Fetch instructor's courses & students count
        courses = Course.objects.filter(instructor=instructor).prefetch_related('enrollment_set')

        total_courses = courses.count()
        total_students = Enrollment.objects.filter(course__instructor=instructor).values('student').distinct().count()

        # Fetch instructor earnings from approved payments
        total_earnings = Payment.objects.filter(course__instructor=instructor, status='approved').aggregate(
            total_earnings=Sum('total_amount')
        )['total_earnings'] or 0

    except Exception as e:
        print(f"Error fetching instructor dashboard data: {e}")
        total_courses = total_students = total_earnings = 0
        profile_picture_url = '/static/home_page_app/images/avatar-placeholder.jpg'

    context = {
        'instructor_user': instructor,
        'profile_picture_url': profile_picture_url,
        'total_courses': total_courses,
        'total_students': total_students,
        'total_earnings': total_earnings,
    }

    return render(request, 'instructor_page_app/instructor_dashboard.html', context)


# -------------------------------------------------------> 2) End: Student and Instructor Dashboard <-------------------------------------------------------



# -------------------------------------------------------> 3) Start: About Course Information <-------------------------------------------------------

# 3.1) course list view
def course_list_view(request):
    """
    View to display the list of courses.
    If the user is logged in, they see only their enrolled courses.
    """
    user = request.user
    courses = Course.objects.select_related('category', 'instructor').prefetch_related('review_set', 'lesson_set')

    try:
        # Show only enrolled courses if the user is a student
        if user.is_authenticated and user.user_type == 'student':
            if Enrollment.objects.filter(student=user).exists():
                courses = courses.filter(enrollment__student=user)

        # Aggregate review ratings, lesson count, and total duration
        courses = courses.annotate(
            average_rating=Avg('review__rating'),
            rating_count=Count('review__id'),
            lessons_count=Count('lesson__id'),
            total_duration=Sum('lesson__duration')
        ).order_by('name')

        # Process the image URLs
        for course in courses:
            course.image_url = f"/media/{course.image}" if course.image else '/static/home_page_app/images/courses/courses-1.jpg'

    except Exception as e:
        print(f"Error fetching courses: {e}")
        courses = []

    # Pagination setup (8 courses per page)
    paginator = Paginator(courses, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'home_page_app/course_list.html', {'page_obj': page_obj})


# 3.2) course detail view
def course_detail_view(request, course_id):
    user = request.user
    has_access = False
    is_enrolled = False
    payment = None
    progress = 0
    completed_lessons = 0

    course = get_object_or_404(Course.objects.select_related('category', 'instructor'), id=course_id)
    lessons = Lesson.objects.filter(course=course).order_by('id')
    total_lessons = lessons.count()
    total_duration = timedelta(0)
    first_video = None
    first_video_html = None

    if user.is_authenticated and user.user_type == 'student':
        enrollment = Enrollment.objects.filter(student=user, course=course).first()
        if enrollment:
            is_enrolled = True
            payment = Payment.objects.filter(student=user, course=course).first()

            # Access rule: if free category OR payment approved
            has_access = bool(course.category.is_free) or (payment and payment.status == 'approved')

            # Progress
            completed_lessons = LessonCompletion.objects.filter(student=user, course=course).count()
            if total_lessons > 0:
                progress = (completed_lessons / total_lessons) * 100

    # Prepare lesson media (unchanged)
    for lesson in lessons:
        lesson.media_available = False
        lesson.video_display = None

        if lesson.video_url:
            if getattr(lesson, 'video_source', '') == 'youtube':
                video_id = extract_youtube_id(lesson.video_url)
                if video_id:
                    embed_url = f'https://www.youtube.com/embed/{video_id}?autoplay=0&rel=0'
                    lesson.video_url = embed_url
                    lesson.video_display = (
                        f'<iframe width="100%" height="500" src="{embed_url}" '
                        'frameborder="0" allow="accelerometer; autoplay; clipboard-write; '
                        'encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>'
                    )
                    lesson.media_available = True
            else:
                lesson.video_url = lesson.video_url.replace('autoplay=true', 'autoplay=false')
                lesson.video_display = lesson.video_url
                lesson.media_available = True

        if not first_video and lesson.video_display:
            first_video = lesson.video_url
            first_video_html = lesson.video_display

        lesson.icon = 'fas fa-play-circle' if (has_access and lesson.media_available) else 'fas fa-lock'

        if getattr(lesson, 'duration', None):
            total_duration += lesson.duration

    total_seconds = int(total_duration.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    reviews = Review.objects.filter(course=course).select_related('student').order_by('-created_at')
    ratings_count = reviews.count()
    average_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0
    rating_display = "{:.1f}".format(average_rating) if average_rating else "No ratings"

    related_courses = Course.objects.filter(category=course.category).exclude(id=course_id).only('id', 'name', 'image', 'course_amount')

    instructor_profile = Profile.objects.filter(user=course.instructor).first()
    instructor_profile_picture = instructor_profile.profile_picture.url if instructor_profile and instructor_profile.profile_picture else None
    instructor_courses_count = Course.objects.filter(instructor=course.instructor).count()

    certificate_url = None
    if user.is_authenticated and progress == 100:
        certificate = Certificate.objects.filter(student=user, course=course).first()
        if certificate:
            certificate_filename = f"certificate_{user.id}_{course_id}.pdf"
            certificate_path = os.path.join(settings.MEDIA_ROOT, 'certificate', certificate_filename)
            certificate_url = f"{settings.MEDIA_URL}certificate/{certificate_filename}"
            if not os.path.exists(certificate_path):
                generate_certificate_pdf(
                    filepath=certificate_path,
                    student_id=user.id,
                    course_id=course_id,
                    issue_date=certificate.issue_date,
                    certification_number=certificate.certification_number,
                )

    learning_objectives = course.learning_objectives.split(',') if course.learning_objectives else []
    requirements = course.requirements.split(',') if course.requirements else []

    context = {
        'course': course,
        'course_image_url': f"/media/{course.image}" if course.image else None,
        'instructor_profile': instructor_profile_picture,
        'category_name': course.category.name,
        'language': course.category.language,
        'lessons': lessons,
        'total_duration_hours': hours,
        'total_duration_minutes': minutes,
        'total_duration_seconds': seconds,
        'related_courses': related_courses,
        'reviews': reviews,
        'rating_display': rating_display,
        'ratings_count': ratings_count,
        'instructor_courses_count': instructor_courses_count,
        'has_access': has_access,
        'is_enrolled': is_enrolled,
        'progress': progress,
        'completed_lessons': completed_lessons,
        'certificate_url': certificate_url,
        'first_video': first_video_html if first_video_html else None,
        'rating_range': range(1, 6),
        'category_is_free': course.category.is_free,
        'payment': payment,
        # ⛔️ Removed: 'expiration_warning', 'expired', 'today'
        'description': course.description,
        'learning_objectives': learning_objectives,
        'requirements': requirements,
    }

    return render(request, 'home_page_app/student_course_details.html', context)


# 3.3) enroll in course
@login_required(login_url='/student/login/')
def dashboard_enrolled_courses(request):
    """
    Fetches and displays the enrolled courses of the logged-in student with progress tracking.
    """
    student = request.user  # Get logged-in user directly

    if student.user_type != 'student':  # Ensure only students access this view
        return redirect('home_page_app:dashboard')  # Redirect if not a student

    try:
        # Fetch the enrolled courses along with their payment status
        enrolled_courses = Enrollment.objects.filter(student=student).select_related('course__category').annotate(
            payment_status=Subquery(
                Payment.objects.filter(
                    student=student,
                    course_id=OuterRef('course_id')
                ).values('status')[:1]  # Fetch first payment status
            )
        ).values(
            'course_id', 
            'course__image', 
            'course__category__name', 
            'payment_status',
            course_name=F('course__name')  # ✅ FIX: Ensures 'course_name' is properly referenced
        )

        # Fetch lesson completion data for progress tracking
        progress_data = {}
        for course in enrolled_courses:
            course_id = course['course_id']
            total_lessons = Lesson.objects.filter(course_id=course_id).count()
            completed_lessons = LessonCompletion.objects.filter(student=student, course_id=course_id).count()

            progress = (completed_lessons / total_lessons) * 100 if total_lessons > 0 else 0

            progress_data[course_id] = {
                'total_lessons': total_lessons,
                'completed_lessons': completed_lessons,
                'progress': progress
            }

        # Categorize courses into active and completed
        active_courses = []
        completed_courses = []

        for course in enrolled_courses:
            course_id = course['course_id']
            course.update(progress_data.get(course_id, {'completed_lessons': 0, 'total_lessons': 0, 'progress': 0}))

            # Determine course status based on payment status and progress
            if course['payment_status'] == 'approved':
                if course['progress'] == 100:
                    course['status'] = 'completed'
                    completed_courses.append(course)
                else:
                    course['status'] = 'active'
                    active_courses.append(course)
            elif course['payment_status'] == 'pending':
                course['status'] = 'pending'
            else:
                course['status'] = 'rejected'

            # Construct full media URL for the course image
            course['course_image_url'] = f'/media/{course["course__image"]}' if course['course__image'] else '/static/home_page_app/images/courses-1.jpg'

        return render(request, 'home_page_app/student_enrolled_courses.html', {
            'all_courses': enrolled_courses,
            'active_courses': active_courses,
            'completed_courses': completed_courses,
        })

    except Exception as e:
        print(f"Error fetching enrolled courses or progress: {e}")
        return render(request, 'home_page_app/student_enrolled_courses.html', {'all_courses': []})




# 3.4) enroll in course for free
@login_required(login_url='/student/login/')
def enroll_in_course_for_free(request, course_id):
    """
    Allows students to enroll in free courses without payment.
    """
    student = request.user  # Get logged-in user directly

    if student.user_type != 'student':  # Ensure only students enroll
        return redirect('home_page_app:dashboard')

    try:
        # Check if the student is already enrolled
        if not Enrollment.objects.filter(student=student, course_id=course_id).exists():
            # Enroll the student in the course
            Enrollment.objects.create(
                enrollment_date=timezone.now().date(),
                student=student,
                course_id=course_id,
                created_at=timezone.now()
            )

            # Create an approved payment record for free courses
            Payment.objects.create(
                expected_course_amount=0,
                total_amount=0,
                payment_date=timezone.now(),
                status='approved',
                student=student,
                course_id=course_id
            )

        return redirect('home_page_app:course_detail', course_id=course_id)

    except Exception as e:
        print(f"Error enrolling in course: {e}")
        return redirect('500.html')



# -------------------------------------------------------> 3) End: About Course Information <-------------------------------------------------------


# -------------------------------------------------------> 4) Start: Course related Information <-------------------------------------------------------

# 4.1) complete lesson
@login_required(login_url='/student/login/')
@csrf_exempt
def complete_lesson(request):
    """
    Marks a lesson as completed for a student and generates a certificate if the course is fully completed.
    """
    if request.method == "POST":
        student = request.user  # Get logged-in student directly
        lesson_id = request.POST.get('lesson_id')
        course_id = request.POST.get('course_id')

        if not lesson_id:
            return JsonResponse({'success': False, 'message': 'Missing lesson ID.'}, status=400)
        if not course_id:
            return JsonResponse({'success': False, 'message': 'Missing course ID.'}, status=400)


        try:
            # Check if the lesson is already marked as completed
            if LessonCompletion.objects.filter(student=student, lesson_id=lesson_id).exists():
                return JsonResponse({'success': False, 'message': 'Lesson already completed.'}, status=400)

            # Mark lesson as completed
            LessonCompletion.objects.create(
                student=student,
                course_id=course_id,
                lesson_id=lesson_id,
                completion_date=timezone.now()
            )

            # Calculate progress
            total_lessons = Lesson.objects.filter(course_id=course_id).count()
            completed_lessons = LessonCompletion.objects.filter(student=student, course_id=course_id).count()
            progress = (completed_lessons / total_lessons) * 100 if total_lessons > 0 else 0

            # Generate a certificate if the course is fully completed
            certificate_url = None
            if completed_lessons == total_lessons:
                if not Certificate.objects.filter(student=student, course_id=course_id).exists():
                    certificate = Certificate.objects.create(
                        issue_date=timezone.now().date(),
                        student=student,
                        course_id=course_id,
                        created_at=timezone.now()
                    )

                    certificate_filename = f"certificate_{student.id}_{course_id}_{certificate.certification_number}.pdf"
                    certificate_path = os.path.join(settings.MEDIA_ROOT, 'certificate', certificate_filename)

                    # Ensure the directory exists
                    os.makedirs(os.path.dirname(certificate_path), exist_ok=True)

                    # Generate certificate PDF
                    generate_certificate_pdf(
                        filepath=certificate_path,
                        student_id=student.id,
                        course_id=course_id,
                        issue_date=certificate.issue_date,
                        certification_number=certificate.certification_number,
                    )
                    certificate_url = f"/media/certificate/{certificate_filename}"

            return JsonResponse({'success': True, 'progress': progress, 'completed_lessons': completed_lessons, 'certificate_url': certificate_url})

        except Exception as e:
            print(f"Error completing lesson: {e}")
            return JsonResponse({'success': False, 'message': f'An error occurred: {str(e)}'}, status=500)

    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=400)


# 4.2) generate certificate PDF
def generate_certificate_pdf(*, filepath, student_id, course_id, issue_date, certification_number):

    try:
        # Fetch student & course details
        student = CustomUser.objects.filter(id=student_id, user_type='student').values(
            'first_name', 'middle_name', 'last_name'
        ).first()
        course = Course.objects.filter(id=course_id).values('name').first()

        if not student:
            raise ValueError(f"Student with ID {student_id} not found")
        if not course:
            raise ValueError(f"Course with ID {course_id} not found")

        # Corrected font path
        font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'LobsterTwo-Regular.ttf')
        
        # Check if font file exists
        if not os.path.exists(font_path):
            raise FileNotFoundError(f"Font file not found: {font_path}")

        # Register font
        pdfmetrics.registerFont(TTFont('CustomFont', font_path))

        # PDF template setup
        template_path = os.path.join(settings.BASE_DIR, 'static', 'certificate_templates', 'certificate_template.pdf')
        logo_path = os.path.join(settings.BASE_DIR, "static", "home_page_app", "images", "logo.png")

        # Check if template PDF exists
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Certificate template not found: {template_path}")

        reader = PdfReader(template_path)
        page = reader.pages[0]
        width, height = float(page.mediabox.upper_right[0]), float(page.mediabox.upper_right[1])

        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=(width, height))

        # Draw logo if exists
        if os.path.exists(logo_path):
            c.drawImage(logo_path, 30, height - 70, width=150, height=50, mask='auto')

        # Certificate text positioning
        student_name_position = (width / 1.83, height - 270)
        course_name_position = (width / 1.83, height - 340)
        issue_date_position = (138, height - 400)
        certification_number_position = (width / 1.50, height - 15)

        # Use custom font for student name
        c.setFont("CustomFont", 24)
        c.drawCentredString(*student_name_position, f"{student['first_name']} {student['middle_name']} {student['last_name']}")

        # Course name
        c.setFillColor(colors.grey)
        c.setFont("Helvetica", 12)
        c.drawCentredString(*course_name_position, f"'{course['name']}'")

        # Issue date (Fix: Use Passed Issue Date Instead of `now()`)
        c.setFillColor(colors.black)
        c.drawString(*issue_date_position, issue_date.strftime('%Y-%m-%d'))  # Use updated issue date

        # Certification number
        c.setFont("Helvetica", 7)
        c.setFillColor(colors.white)
        c.drawCentredString(*certification_number_position, f"{certification_number}")

        c.save()
        packet.seek(0)

        # Merge the generated text onto the template
        new_pdf = PdfReader(packet)
        page.merge_page(new_pdf.pages[0])

        writer = PdfWriter()
        writer.add_page(page)

        with open(filepath, "wb") as output_file:
            writer.write(output_file)

        # print(f"Certificate successfully generated: {filepath}")

    except Exception as e:
        print(f"Error in generating certificate: {str(e)}")
        raise 



# 4.3) review submission
@login_required(login_url='/student/login/')
def submit_review(request, course_id):
    """
    Submits a review for a course.
    """
    if request.method == 'POST':
        student = request.user  # Get logged-in student

        rating = request.POST.get('rating')
        review_text = request.POST.get('review_text', '').strip()

        if not rating or not review_text:
            return redirect(reverse('home_page_app:course_detail', args=[course_id]))

        try:
            rating = int(rating)
        except ValueError:
            return redirect(reverse('home_page_app:course_detail', args=[course_id]))

        # Validate course existence
        course = get_object_or_404(Course, id=course_id)

        # Create the review
        Review.objects.create(
            review_text=review_text,
            rating=rating,
            student=student,
            course=course,
            created_at=timezone.now()
        )

        return redirect(reverse('home_page_app:student_dashboard'))

    return redirect(reverse('home_page_app:course_detail', args=[course_id]))


# 4.4) payment submission
@login_required(login_url='/student/login/')
def submit_payment_view(request):
    """
    Submits a payment for a course.
    """
    if request.method == 'POST':
        student = request.user  # Get logged-in student

        course_id = request.POST.get('course_id')
        sender_phone_number = request.POST.get('sender_phone_number')
        course_amount = request.POST.get('course_amount')

        course = get_object_or_404(Course, id=course_id)

        # Insert the payment record
        Payment.objects.create(
            expected_course_amount=course_amount,
            total_amount=course_amount,
            payment_date=timezone.now(),
            sender_phone_number=sender_phone_number,
            status='pending',
            student=student,
            course=course
        )

        # Ensure student is enrolled
        Enrollment.objects.get_or_create(
            student=student,
            course=course,
            defaults={'enrollment_date': timezone.now().date(), 'created_at': timezone.now()}
        )

        return redirect('home_page_app:payment_confirmation')

    return redirect('home_page_app:course_detail', course_id=course_id)


# 4.5) confrimation about payment
def payment_confirmation(request):
    return render(request, 'home_page_app/student_payment_confirmation.html')

# 4.6) purchase veiw
@login_required(login_url='/student/login/')
def purchase_view(request, course_id):
    try:
        # Fetch course details using ORM
        course = Course.objects.select_related('instructor').filter(id=course_id).values(
            'id', 'name', 'course_amount', 'instructor__first_name', 'instructor__last_name'
        ).first()

        if not course:
            return render(request, '404.html')

        context = {
            'course': course,
            'student_user': request.user if request.user.user_type == 'student' else None,
        }
        return render(request, 'home_page_app/student_purchase.html', context)

    except Exception as e:
        print(f"Error fetching purchase view: {e}")
        return render(request, '500.html')


# 4.7) purchase history
@login_required(login_url='/student/login/')
def purchase_history(request):
    """
    Displays the purchase history of a student.
    """
    student = request.user  # Get logged-in student

    # Fetch the purchase history
    purchases = Payment.objects.filter(student=student).select_related('course').values(
        'id', 'total_amount', 'status', 'payment_date', 'course__name', 'course__image'
    )

    # Process image URLs
    for purchase in purchases:
        purchase['course_image_url'] = f'/media/{purchase["course__image"]}' if purchase['course__image'] else '/static/home_page_app/images/courses/courses-8.jpg'

    return render(request, 'home_page_app/dashboard_purchase_history.html', {'purchases': purchases})


# 4.8) course review view
@login_required(login_url='/student/login/')
def review_view(request):
    return render(request, "home_page_app/dashboard_review.html")

# 4.9) Course Edit Feedback View
@login_required(login_url='/student/login/')
def edit_feedback_view(request, review_id):
    review = get_object_or_404(Review.objects.select_related('course'), id=review_id)

    if request.method == 'POST':
        review_text = request.POST.get('review_text')
        rating = request.POST.get('rating')
        
        review.review_text = review_text
        review.rating = rating
        review.save()

        return JsonResponse({'success': True})

    # Ensure course name is passed to the template
    context = {
        'review': review,
        'course_name': review.course.name  # Pass course name
    }
    
    return render(request, 'home_page_app/dashboard_review_update.html', context)


# 4.10) course certificates view
@login_required(login_url='/student/login/')
def certificates_view(request):
    return render(request, 'home_page_app/dashboard_certificates.html')


# 4.11) event list view
@login_required(login_url='/student/login/')
def event_list_view(request):
    """
    Fetches events related to courses that the logged-in student is enrolled in.
    """
    student = request.user  # Get logged-in student

    if student.user_type == 'student':
        events = Event.objects.filter(course__enrollment__student=student).select_related('course').order_by('-event_date')
    else:
        events = Event.objects.select_related('course').order_by('-event_date')

    return render(request, 'home_page_app/event_list.html', {'events': events})


# 4.12) Event Detail View
@login_required(login_url='/student/login/')
def event_detail_view(request, id):
    try:
        event = Event.objects.select_related('course').get(id=id)
        is_enrolled = Enrollment.objects.filter(student=request.user, course=event.course).exists()

        event_data = {
            'id': event.id,
            'name': event.name,
            'description': event.description,
            'event_date': event.event_date,
            'event_time': event.event_time,
            'event_place': event.event_place,
            'event_status': event.event_status,
            'course_amount': event.course.course_amount,
            'course_image': f"{settings.MEDIA_URL}{event.course.image}" if event.course.image else None,
        }

        return render(request, 'home_page_app/event_details.html', {'event': event_data, 'is_enrolled': is_enrolled})

    except Event.DoesNotExist:
        return render(request, '404.html')

    except Exception as e:
        print(f"Error in event_detail_view: {str(e)}")
        return render(request, '500.html')


# 4.13) Search Certificates View
def search_certificates(request):
    query = request.GET.get('q', '')
    certificates = Certificate.objects.filter(
        Q(student__first_name__icontains=query) |
        Q(student__middle_name__icontains=query) |
        Q(student__last_name__icontains=query) |
        Q(student__email__icontains=query) |
        Q(certification_number__icontains=query) |
        Q(course__name__icontains=query)
    ) if query else []

    certificate_list = []
    for certificate in certificates:
        student_id = certificate.student.id
        course_id = certificate.course.id
        cert_number = certificate.certification_number
        certificate_filename = f"certificate_{student_id}_{course_id}_{cert_number}.pdf"
        certificate_path = os.path.join(settings.MEDIA_ROOT, 'certificate', certificate_filename)
        certificate_url = f"{settings.MEDIA_URL}certificate/{certificate_filename}"

        # Generate the certificate if not already created
        if not os.path.exists(certificate_path):
            generate_certificate_pdf(
                filepath=certificate_path,
                student_id=student_id,
                course_id=course_id,
                issue_date=certificate.issue_date,
                certification_number=cert_number,
            )

        certificate_list.append({
            'student_name': f"{certificate.student.first_name} {certificate.student.middle_name} {certificate.student.last_name}",
            'course_name': certificate.course.name,
            'certification_number': cert_number,
            'issue_date': certificate.issue_date,
            'download_url': certificate_url,
        })

    return render(request, 'home_page_app/search_certificates.html', {
        'certificates': certificate_list,
        'query': query,
    })

    

# 4.14) Course Category View
def course_category_view(request, category_id):
    category = get_object_or_404(Category, id=category_id)

    # Filter courses based on login status
    if request.user.is_authenticated and request.user.user_type == 'student':
        courses = Course.objects.filter(category=category, enrollment__student=request.user)
    else:
        courses = Course.objects.filter(category=category)

    courses = courses.select_related('instructor', 'category').prefetch_related('review_set')

    course_data = []
    for course in courses:
        # Handle images
        image_url = f"/media/{course.image}" if course.image else "/static/home_page_app/images/courses-1.jpg"

        # Calculate ratings
        rating_data = course.review_set.aggregate(
            average_rating=Avg('rating'),
            rating_count=Count('rating')
        )

        rating_display = "{:.1f}".format(rating_data['average_rating']) if rating_data['average_rating'] else "0.0"
        rating_width = (rating_data['average_rating'] / 5) * 100 if rating_data['average_rating'] else 0

        course_data.append({
            'id': course.id,
            'name': course.name,
            'description': course.description,
            'course_amount': course.course_amount,
            'image_url': image_url,
            'start_date': course.start_date,
            'end_date': course.end_date,
            'instructor_first_name': course.instructor.first_name,
            'instructor_last_name': course.instructor.last_name,
            'category_name': course.category.name,
            'category_is_free': course.category.is_free,
            'rating_display': rating_display,
            'rating_width': rating_width,
            'rating_count': rating_data['rating_count'] if rating_data else 0
        })

    return render(request, 'home_page_app/course_category.html', {'courses': course_data})

# -------------------------------------------------------> 4) End: Course related Information <-------------------------------------------------------


# -------------------------------------------------------> 5) Start: Others does not work but still here <-------------------------------------------------------


# 5.1) instructor list view
def instructor_list_view(request):
    return render(request, "home_page_app/instructor_list.html")

# 5.2) instructor detail view
def instructor_detail_view(request, id):
    return render(request, "home_page_app/intructor_details.html", {'id': id})

# 5.3) checkout view
def checkout_view(request):
    return render(request, "home_page_app/checkout.html")

# 5.4) wish list view
def wish_list(request, id):
    return render(request, "home_page_app/dashboard_wish_list.html", {'id': id})

# 5.5) quiz attempts view
def quiz_attempts(request, id):
    return render(request, "home_page_app/dashboard_quiz_attempts.html", {'id': id})

# 5.6) quiz attempt detail view
def quiz_attempt_detail(request, id):
    return render(request, "home_page_app/dashboard_quiz_attempt_detail.html", {'id': id})

# 5.7) Zoom about it view
def zoom_meeting_list_view(request):
    return render(request, "home_page_app/zoom_meeting_list.html")
    
# 5.8) Zoom meeting detail view
def zoom_meeting_detail_view(request, id):
    return render(request, "home_page_app/zoom_meeting_detail.html", {'id': id})

# -------------------------------------------------------> 5) End: Others does not work but still here <-------------------------------------------------------
