import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

msg = EmailMessage()
msg["Subject"] = "Teste TanureFindPrice"
msg["From"] = os.getenv("SMTP_USER")
msg["To"] = os.getenv("EMAIL_TO")
msg.set_content("Teste de envio de e-mail do TanureFindPrice.")

with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT"))) as smtp:
    smtp.starttls()
    smtp.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
    smtp.send_message(msg)

print("E-mail enviado com sucesso!")