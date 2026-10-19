# صورة خفيفة لتشغيل البوت على أي استضافة (VPS / Fly.io / Railway)
FROM python:3.12-slim

# إعدادات بايثون للإنتاج
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# التبعيات أولاً (طبقة cache منفصلة لبناء أسرع)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# كود المشروع
COPY src/ ./src/

# مستخدم غير جذري (أمان)
RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser

# المنفذ الافتراضي للـ Webhook
EXPOSE 8000

# نقطة التشغيل الموحّدة: Webhook + الحلقة الحية + بوت تليجرام معاً.
CMD ["python", "-m", "tradingbot.main"]
