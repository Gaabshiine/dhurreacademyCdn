# urls.py
from django.urls import path
from . import views

app_name = "home_page_app"

urlpatterns = [
    # 1) General views
    path("", views.home_view, name="home"),
    path("about/", views.about_view, name="about"),
    path("contact/", views.contact_view, name="contact"),
    path('search/', views.search_results_view, name='search_results'),

    # 2) Dashboard views - student and instructor
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),  # 
    path('instructor/dashboard/', views.instructor_dashboard, name='instructor_dashboard'), 

    # 3) About course information
    path('courses/', views.course_list_view, name='course_list'),  
    path('course/<int:course_id>/', views.course_detail_view, name='course_detail'),
    path('course/<int:course_id>/enroll/', views.enroll_in_course_for_free, name='enroll_in_course_for_free'),
    path('enrolled_courses/', views.dashboard_enrolled_courses, name='enrolled_courses'),

    # 4) Course-related information
    path('complete-lesson/', views.complete_lesson, name='complete_lesson'),

    path('certificates/', views.certificates_view, name='certificates'),
    path('search/certificate/', views.search_certificates, name='search_certificates'),

    path('category/<int:category_id>/', views.course_category_view, name='course_category'),

    path('course/<int:course_id>/submit-review/', views.submit_review, name='submit_review'),
    path('reviews/', views.review_view, name='review'),
    path('edit_feedback/<int:review_id>/', views.edit_feedback_view, name='edit_feedback'),

    path("event_list/", views.event_list_view, name="event_list"),
    path("event_detail/<int:id>/", views.event_detail_view, name="event_detail"),

    path('submit_payment/', views.submit_payment_view, name='submit_payment'),
    path('purchase/<int:course_id>/', views.purchase_view, name='purchase'),
    path('purchase-history/', views.purchase_history, name='purchase_history'),
    path('payment/confirmation/', views.payment_confirmation, name='payment_confirmation'),

    # 5) Other non-functional views (placeholders)
    path("zoom_meeting_list/", views.zoom_meeting_list_view, name="zoom_meeting_list"),
    path("zoom_meeting_detail/<int:id>/", views.zoom_meeting_detail_view, name="zoom_meeting_detail"),
    path("instructor_list/", views.instructor_list_view, name="instructor_list"),
    path("instructor_detail/<int:id>/", views.instructor_detail_view, name="instructor_detail"),
    path("checkout/", views.checkout_view, name="checkout"),
    path("wish_list/<int:id>/", views.wish_list, name="wish_list"),
    path("quiz_attempts/<int:id>/", views.quiz_attempts, name="quiz_attempts"),
    path("quiz_attempt_detail/<int:id>/", views.quiz_attempt_detail, name="quiz_attempt_detail"),
]
