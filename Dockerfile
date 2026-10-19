# Dockerfile في جذر الريبو — يبني بوت التداول من مجلد trading-bot.
# موجود هنا ليشتغل على منصات النشر (CranL/Railway/…) التي تبني من الجذر.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# التبعيات أولاً (طبقة cache منفصلة)
COPY trading-bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# كود البوت
COPY trading-bot/src/ ./src/

# مستخدم غير جذري (أمان)
RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# الافتراضي: خادم الـ Webhook. للحلقة الحية، غيّر الأمر في إعدادات المنصة إلى:
#   python -m tradingbot.run_live AAPL MSFT NVDA
CMD ["uvicorn", "tradingbot.serve:app", "--host", "0.0.0.0", "--port", "8000"]
