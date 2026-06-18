# استفاده از ایمیج رسمی و سبک پایتون
FROM python:3.11-slim

# تنظیم متغیرهای محیطی پایتون برای اجرای بهتر در داکر
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# ساخت پوشه کاری
WORKDIR /app

# نصب پکیج‌های پیش‌نیاز سیستمی در صورت نیاز
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# کپی کردن فایل نیازمندی‌ها و نصب آنها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی کردن تمام سورس کدهای پروژه
COPY . .

# مشخص کردن کامند اصلی برای اجرا (اجرای بات اصلی)
CMD ["python", "app/main.py"]
