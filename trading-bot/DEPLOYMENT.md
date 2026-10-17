# 🚀 دليل النشر (Deployment)

تشغيل البوت 24/7 على استضافة. الخيار الموصى به: **VPS + Docker**.

> ⚠️ أمان: لا تضع مفاتيحك في أي ملف يُرفع لـ Git. استخدم `.env` على السيرفر
> فقط (مستبعد عبر `.gitignore` و`.dockerignore`). لا تشارك المفاتيح مع أحد.

---

## الخيار 1: VPS + Docker (موصى به)

### 1. جهّز سيرفر (DigitalOcean / Hetzner / Contabo ~5$/شهر)
نظام Ubuntu 22.04، ثبّت Docker:
```bash
curl -fsSL https://get.docker.com | sh
```

### 2. انسخ المشروع وجهّز الأسرار
```bash
git clone https://github.com/omaralenezi52/botTrade.git
cd botTrade/trading-bot
cp .env.example .env
nano .env        # املأ مفاتيحك (Alpaca, Anthropic, Telegram, WEBHOOK_SECRET)
```

### 3. شغّل
```bash
docker compose up -d --build        # يبني ويشغّل في الخلفية
docker compose logs -f live         # متابعة سجلّ الحلقة الحية
docker compose ps                   # حالة الخدمات
```
`restart: always` يعيد تشغيل البوت تلقائياً لو تعطّل أو أُعيد إقلاع السيرفر.

### 4. التحكّم
```bash
docker compose restart live         # إعادة تشغيل الحلقة
docker compose down                 # إيقاف الكل
docker compose up -d --build        # بعد تحديث الكود
```

---

## الخيار 2: systemd (بدون Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
أنشئ `/etc/systemd/system/aegisbot.service`:
```ini
[Unit]
Description=Trading Bot Live Loop
After=network.target

[Service]
WorkingDirectory=/root/botTrade/trading-bot
Environment=PYTHONPATH=/root/botTrade/trading-bot/src
EnvironmentFile=/root/botTrade/trading-bot/.env
ExecStart=/root/botTrade/trading-bot/.venv/bin/python -m tradingbot.run_live AAPL MSFT NVDA
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```
```bash
systemctl enable --now aegisbot
systemctl status aegisbot
journalctl -u aegisbot -f        # السجلّ المباشر
```

---

## ضبط الإعدادات (`.env`)

```env
# الوضع — ابدأ دائماً بـ ADVISOR ثم SEMI_AUTO ثم FULL_AUTO
TRADE_MODE=ADVISOR

# المنصة
BROKER=alpaca
ALPACA_API_KEY=...
ALPACA_SECRET_KEY=...
ALPACA_PAPER=true            # true = تجريبي (ابدأ هنا أسابيع)

# الذكاء
ANTHROPIC_API_KEY=...

# تليجرام (الإشعارات)
TELEGRAM_TOKEN=...
TELEGRAM_CHAT_ID=...

# أمان الـ Webhook (لو تستخدمه)
WEBHOOK_SECRET=سلسلة-عشوائية-طويلة
```

---

## خطة الإطلاق الآمنة

```
1. ADVISOR + Paper     → توصيات على تليجرام، تراقب أسابيع
2. SEMI_AUTO + Paper   → تضغط موافقة، تتأكد من التنفيذ
3. FULL_AUTO + Paper   → آلي كامل على التجريبي، تقيس المقاييس
4. FULL_AUTO + Live    → مبلغ صغير فقط بعد إثبات الأداء
```

⚠️ لا تنتقل لـ Live (`ALPACA_PAPER=false`) إلا بعد أسابيع من أداء Paper مُثبت.

---

## HTTPS للـ Webhook (لو تستخدم TradingView)

ضع reverse proxy (Caddy أمثلها) أمام المنفذ 8000 لإنهاء TLS:
```
yourdomain.com {
    reverse_proxy localhost:8000
}
```
Caddy يجلب شهادة HTTPS تلقائياً. TradingView يتطلب HTTPS.
