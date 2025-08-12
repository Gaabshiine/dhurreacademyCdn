
from django.core.mail import send_mail
import re

# def send_expiration_email(user, course, is_soon=False):
#     """
#     Sends an expiration email to the student for their enrolled course.
    
#     :param user: CustomUser instance (student)
#     :param course: Course instance
#     :param is_soon: Boolean indicating whether the course is expiring soon or already expired.
#     """
#     subject = "Course Expiration Notice"
    
#     if is_soon:
#         message = (
#             f"Dear {user.first_name},\n\n"
#             f"Your course '{course.name}' is expiring soon. You have less than 10 days to complete it.\n"
#             "Please log in and complete your remaining lessons.\n\n"
#             "Thank you for choosing us!"
#         )
#     else:
#         message = (
#             f"Dear {user.first_name},\n\n"
#             f"Your course '{course.name}' has expired. Unfortunately, you no longer have access to the lessons.\n"
#             "If you need help or want to renew access, please contact our support team.\n\n"
#             "Thank you for choosing us!"
#         )

#     send_mail(subject, message, 'no-reply@skillup24academy.com', [user.email])

def extract_youtube_id(url):
    """Extract YouTube video ID from various URL formats"""
    patterns = [
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([^"&?\/\s]{11})',
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([^"&?\/\s]{11})',
        r'(?:https?:\/\/)?(?:www\.)?youtu\.be\/([^"&?\/\s]{11})',
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/v\/([^"&?\/\s]{11})',
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/user\/[^\/]+\/?#?\/[^\/]*\/([^"&?\/\s]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match and match.group(1):
            return match.group(1)
    return None
