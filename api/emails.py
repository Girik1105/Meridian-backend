from django.conf import settings
from django.core.mail import send_mail


def send_welcome_email(user):
    subject = "Welcome to Meridian — Your AI Career Mentor"
    frontend_url = settings.FRONTEND_URL

    plain_text = (
        f"Hi {user.first_name or user.username},\n\n"
        "Welcome to Meridian! We're excited to help you explore your career potential.\n\n"
        "Here's what you can do:\n"
        "- Have a conversation with your AI career mentor to map out where you are\n"
        "- Discover personalized career paths based on your unique background\n"
        "- Try 30-minute skill tasters to test-drive new skills before committing\n\n"
        f"Get started: {frontend_url}/dashboard\n\n"
        "— The Meridian Team"
    )

    html_message = f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background-color:#F9FAFB;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#F9FAFB;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
          <!-- Header -->
          <tr>
            <td style="background-color:#1A1B2F;padding:32px 40px;border-radius:12px 12px 0 0;">
              <h1 style="margin:0;color:#E8973A;font-size:28px;font-weight:700;letter-spacing:-0.5px;">
                Meridian
              </h1>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="background-color:#FFFFFF;padding:40px;">
              <h2 style="margin:0 0 16px;color:#1A1B2F;font-size:22px;font-weight:600;">
                Welcome, {user.first_name or user.username}!
              </h2>
              <p style="margin:0 0 24px;color:#374151;font-size:16px;line-height:1.6;">
                You've just taken the first step toward discovering career paths that actually fit your life. Meridian is your AI-powered career mentor — here to help you understand where you are, show you where you could go, and let you try before you commit.
              </p>
              <!-- Feature callout -->
              <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#FBE8D0;border-radius:8px;margin-bottom:28px;">
                <tr>
                  <td style="padding:24px;">
                    <p style="margin:0 0 12px;color:#1A1B2F;font-size:15px;font-weight:600;">Here's what's waiting for you:</p>
                    <p style="margin:0 0 8px;color:#374151;font-size:14px;line-height:1.5;">
                      <strong style="color:#C47A2E;">Know Me</strong> — A guided conversation to map your background, goals, and constraints
                    </p>
                    <p style="margin:0 0 8px;color:#374151;font-size:14px;line-height:1.5;">
                      <strong style="color:#C47A2E;">Show Me the Way</strong> — Personalized career paths grounded in real market data
                    </p>
                    <p style="margin:0;color:#374151;font-size:14px;line-height:1.5;">
                      <strong style="color:#C47A2E;">Try Before You Commit</strong> — 30-minute skill tasters so you can test-drive before deciding
                    </p>
                  </td>
                </tr>
              </table>
              <!-- CTA Button -->
              <table cellpadding="0" cellspacing="0" style="margin:0 auto;">
                <tr>
                  <td style="border-radius:8px;background-color:#E8973A;">
                    <a href="{frontend_url}/dashboard"
                       style="display:inline-block;padding:14px 32px;color:#FFFFFF;font-size:16px;font-weight:600;text-decoration:none;border-radius:8px;">
                      Get Started
                    </a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <!-- Divider -->
          <tr>
            <td style="background-color:#FFFFFF;padding:0 40px;">
              <hr style="border:none;border-top:1px solid #D1D5DB;margin:0;">
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background-color:#FFFFFF;padding:24px 40px 32px;border-radius:0 0 12px 12px;">
              <p style="margin:0;color:#6B7280;font-size:13px;line-height:1.5;text-align:center;">
                Meridian is an AI career mentor, not a licensed career counselor.<br>
                Always cross-reference suggestions with human advisors.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    send_mail(
        subject=subject,
        message=plain_text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=True,
    )
