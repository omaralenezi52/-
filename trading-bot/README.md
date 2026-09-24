# 🤖 Trading Bot — نظام توصيات وتداول بحاكم مخاطر صارم

نواة نظام تداول مبنية على **ترابط القرارات (Confluence)** و**حاكم مخاطر حتمي**
يحكم كل صفقة. الفلسفة: *الذكاء الاصطناعي يقترح، وكود المخاطر الحتمي يقرر.*

> ⚠️ **تنويه مهم:** هذا النظام أداة **مساعدة قرار بإدارة مخاطر**، ولا يضمن أرباحاً.
> لا يوجد بوت في العالم يضمن ربحاً ثابتاً لأن السوق لا يتحكم فيه أحد. قوة النظام
> في الانضباط وحماية رأس المال، لا في التنبؤ السحري.

## المعمارية

```
TradingView (Webhook: إشارة خام من Pine Script)
        ▼
FastAPI Webhook آمن  ── توكن سري + تحقق Pydantic + HTTPS
        ▼
Pipeline (ترابط القرارات):
  DecisionEngine (توافق أدلة + نظام السوق)
        ▼
  RiskEngine (الحاكم: حجم من الوقف، R:R، حد خسارة يومي، انكشاف)
        ▼
  Recommendation (توصية بالأرقام)
        ▼
  ┌────────────┬──────────────┬─────────────┐
  Telegram     IBKR Adapter   Derayah
  (توصية)      (تنفيذ آلي)    (إشعار فقط)
```

## البنية

| المجلد | المسؤولية |
|---|---|
| `domain/models.py` | النماذج الأساسية (Signal, TradePlan, Recommendation...) |
| `domain/risk.py` | **حاكم المخاطر** — يعتمد/يرفض ويحسب الحجم |
| `domain/decision.py` | محرك التوافق وكشف نظام السوق |
| `domain/features.py` | حساب المؤشرات (numpy/pandas) وتحويلها لأدلة |
| `agent/analyst.py` | **عقدة المحلل الذكي** (Claude) — سياق + فيتو + شرح |
| `backtest/engine.py` | محرك الاختبار التاريخي (بلا Look-ahead) |
| `backtest/metrics.py` | مقاييس الأداء (شارب، تراجع، عامل ربح...) |
| `pipeline.py` | ربط القرارات من الإشارة إلى التوصية (مع/بدون ذكاء) |
| `webhook/app.py` | مستقبِل TradingView الآمن |
| `notify/telegram.py` | تنسيق وإرسال التوصيات |
| `adapters/` | محوّلات المنصات (Paper / IBKR / Derayah) |

## نقاط الأمان المُغلقة

- توكن سري إلزامي في كل Webhook (مقارنة ثابتة الزمن `compare_digest`).
- تحقق صارم من المدخلات عبر Pydantic — لا ثقة بأي JSON وارد.
- `Decimal` لكل الحسابات المالية (لا أخطاء `float`).
- مفتاح تفرّد (Idempotency) لكل أمر يمنع التكرار عند انقطاع الشبكة.
- وقف خسارة إجباري في كل خطة صفقة (لا صفقة بلا حماية).
- قاطع خسارة يومي يوقف التداول عند تجاوز الحد.
- أسرار من متغيّرات البيئة فقط (`.env` خارج Git).

## التشغيل

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # ثم عدّل القيم (WEBHOOK_SECRET إلزامي)

# الاختبارات
pytest

# تشغيل النظام الكامل (Webhook + تحليل + تنفيذ) خلف HTTPS في الإنتاج
uvicorn tradingbot.serve:app --host 0.0.0.0 --port 8000
```

### ربط منصتك (تحط بياناتك في `.env` فقط)

```env
BROKER=ibkr            # paper | ibkr | derayah
IBKR_HOST=127.0.0.1
IBKR_PORT=7497         # 7497 = Paper، 7496 = Live (ابدأ Paper)
IBKR_CLIENT_ID=1
ANTHROPIC_API_KEY=...  # لتفعيل طبقة الذكاء (فارغ ⇒ محلل محايد آمن)
TRADE_MODE=ADVISOR     # ADVISOR (توصية) → SEMI_AUTO → FULL_AUTO
```

لتفعيل IBKR: شغّل TWS أو IB Gateway، فعّل API في إعداداتهما، ثم
`pip install ib_insync` وضع `BROKER=ibkr`. الكود يلتقط الباقي تلقائياً.

## خريطة الطريق

- [x] النواة: نماذج + حاكم مخاطر + محرك قرار + Pipeline + اختبارات
- [x] مستقبِل Webhook آمن + إشعار تليجرام
- [x] محرك المؤشرات (numpy/pandas) — حساب بتحكم كامل
- [x] طبقة الذكاء (Claude) — سياق + فيتو + تعديل ثقة (تراجع آمن بلا مفتاح)
- [x] محرك Backtesting + مقاييس (Sharpe / Sortino / Drawdown / Win rate / Profit factor)
- [x] ربط IBKR الفعلي (`ib_insync`) + تجميع كامل (Wiring) جاهز للبيانات
- [ ] أزرار موافقة تليجرام (وضع SEMI_AUTO)
- [ ] Paper trading أسابيع قبل أي حساب حقيقي

## الاختبار التاريخي

```bash
# بيانات اصطناعية (عرض)
python -m tradingbot.backtest.run_demo
# على بياناتك (CSV بأعمدة open,high,low,close,volume)
python -m tradingbot.backtest.run_demo data/aapl_1h.csv
```

⚠️ نتائج الاختبار التاريخي **ليست ضماناً** للمستقبل. تُستخدم لقياس الأفضلية
الإحصائية ومقارنة الاستراتيجيات، ويجب أن تتبعها فترة Paper trading.

## أوضاع التشغيل

| الوضع | السلوك |
|---|---|
| `ADVISOR` | توصية فقط، التنفيذ يدوي (ابدأ هنا) |
| `SEMI_AUTO` | ينتظر موافقتك في تليجرام ثم ينفّذ |
| `FULL_AUTO` | ينفّذ آلياً ضمن حدود المخاطر (بعد إثبات طويل) |
