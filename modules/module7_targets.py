"""
modules/module7_targets.py
──────────────────────────
Module 7 — العملاء المستهدفة (Target Customers) using Polars.
Works on the main portfolio file (المحفظة الموزعة).

DOUBLE FILTER RULE:
1. Primary Filter: Main Status in ('سداد جزئي', 'واعد بالسداد', 'متابعة', 'متوفي') OR Sub Status contains ('الورثة واعدين', 'ورثة').
2. Secondary Filter: Must contain a STRICT POSITIVE KEYWORD (including pay dates: يوم 1..31, ع راتب, بسدد اول الشهر, مواطن, تقاعد, ان شاء الله, etc.).
3. Must NOT contain any disqualifying negative response or full payment.
"""
from __future__ import annotations

import logging
from typing import Dict

import polars as pl

_log = logging.getLogger("Module7_Targets")

POSITIVE = "مستهدف"
NEGATIVE = "غير مستهدف"

# ── 1. Full Payment Disqualification (تم السداد بالكامل) ────────────────────────
FULLY_PAID_KEYWORDS = [
    "تم السداد", "سدد كامل", "كامل المديونية", "كامل المديونيه", "كامل المبلغ",
    "سداد كامل", "مسدد بالكامل", "سدد المديونية كامله", "سدد المديونية كاملة",
    "تم سداد كامل", "خلاص سدد", "تم سداد المبلغ كاملا", "مسدد كامل"
]

# ── 2. Primary Status Allowed Criteria ──────────────────────────────────────────
PRIMARY_MAIN_STATUSES = ["سداد جزئي", "واعد بالسداد", "متابعة", "متوفي"]
PRIMARY_SUB_STATUSES  = ["الورثة واعدين", "ورثة واعدين", "ورثة", "واعدين"]

# ── 3. Strict Positive Keyword Dictionaries by Category ────────────────────────
# توليد أيام الشهر 1 إلى 31 تلقائياً (يوم 1, يوم 27, يوم 28 ...)
DAY_KEYWORDS = [f"يوم {i}" for i in range(1, 32)] + [f"يوم{i}" for i in range(1, 32)]

TARGET_CATEGORIES = {
    "💰 مرتبطة بالراتب والدخل": [
        "بعد الراتب", "بعد نزول الراتب", "بعد استلام الراتب", "مع الراتب", "عند نزول الراتب", "راتبي ينزل",
        "بعد القبض", "بعد المعاش", "وجود فلوس", "توفرت الفلوس", "توفرت السيولة", "معايا فلوس", "وصل الراتب",
        "استلم الراتب", "هيقبض", "قبض", "استلم", "الراتب", "معاش", "تقاعد", "التقاعد", "دعم حكومي",
        "حساب مواطن", "حساب المواطن", "مواطن", "المواطن", "ع مواطن", "ع المواطن",
        "حساب ضمان", "ع ضمان", "ع الضمان", "الضمان الاجتماعي", "الضمان", "ضمان",
        "مستحقات", "مستحقاتي", "مستحقاته"
    ],
    "🤝 وعود بالسداد وتأكيدات": [
        "وعد بالسداد", "وعد", "واعد", "واعد بالسداد", "تم الوعد", "تم الاتفاق", "اتفق", "اتفقنا", "موافق", "وافق",
        "ملتزم", "التزم", "ملتزم بالسداد", "ملتزم بالدفع", "منتظم", "عميل منتظم", "استجاب",
        "إن شاء الله", "ان شاء الله", "ان شاء الل", "انشالله", "بإذن الله", "باذن الله", "بذن الله",
        "أكيد", "اكيد", "أكيد بسدد", "اكيد هسدد", "ابشر", "أبشر", "تم التأكيد", "أكد", "أكد السداد",
        "تسوية", "تسويه", "جدولة", "جدوله"
    ],
    "📅 مرتبطة بتاريخ أو وقت محدد": [
        "اليوم", "باليوم", "خلال اليوم", "قبل نهاية اليوم", "آخر اليوم", "نهاية اليوم",
        "غداً", "غدا", "بكره", "بكرة", "باجر",
        "بعد العصر", "بعد المغرب", "بعد العشاء",
        "بداية الاسبوع", "منتصف الاسبوع", "نهاية الاسبوع",
        "بداية الشهر", "اول الشهر", "أول الشهر", "اول شهر", "أول شهر", "بداية الشهر القادم", "بداية الشهر الجاي",
        "آخر الشهر", "اخر الشهر", "اخر شهر", "آخر شهر", "نهاية الشهر", "مع نهاية الشهر"
    ] + DAY_KEYWORDS,
    "💳 مرتبطة بتحويل أو إيداع أو دفعات": [
        "السداد", "سداد", "يسدد", "بيسدد", "بسدد", "سدد", "هيسدد", "هسدد", "حيسدد", "راح يسدد", "سوف يسدد", "سيتم السداد", "بسداد",
        "دفع", "يدفع", "هدفع", "بدفع", "قسط", "القسط", "دفعة", "دفعه", "هيدفع دفعة", "جزء", "جزئي", "سداد جزئي", "دفعة أولى", "دفعة ثانية",
        "هيحول", "حول", "تحويل", "تحويل بنكي", "إيداع", "ايداع",
        "الباقي", "باقي", "ايصال", "إيصال", "فاتورة", "فاتوره"
    ]
}

# ── 4. Disqualifying Negative / Non-Contact / Stall / Typo Keywords ────────────
DISQUALIFY_KEYWORDS = [
    # Explicit refusals from user prompt
    "رافض يسدد", "رفض السداد", "رفض الدفع", "يرفض السداد", "يرفض الدفع",
    "رافضين السداد", "رافضين سداد", "رافضين", "رافضين يدفعوا", "رافضين يسددوا",
    "لن يسدد", "لن يدفع", "مش هيسدد", "مش بيسدد", "ما هيسدد", "ما بيسدد", "مابيسدد", "ما بسدد", "مابسدد",
    "لا يسدد", "لا يدفع", "غير ملتزم", "غير ملتزم بالسداد", "غير موافق", "غير راغب",
    "مستحيل يسدد", "مو بيسدد", "ما راح يسدد", "ماراح يسدد", "ما رح يسدد",
    "لا يريد السداد", "امتنع عن السداد", "رفض التعاون", "منزعج", "شؤون قانونية", "شؤون قانونيه",
    
    # Financial inability / No money
    "ما معه فلوس", "مامعه فلوس", "ما معاه فلوس", "مامعاه فلوس", "ما عنده فلوس", "ماعنده فلوس", "طفران", "طفاران",
    
    # Non-contact & Call drops
    "أغلق الخط", "سكر الخط", "قفل الخط", "يسكر الخط", "قفل", "قفلت", "يكنسل", "كنسل",
    "لا يرد", "لم يرد", "لا يوجد رد", "لا يجيب", "ما يرد", "مايرد", "لابرد", "لا ترد", "لا رد",
    "خارج التغطية", "مغلق", "بيزي", "مشغول", "ما يمسك", "م بيشبك", "م يشبك", "ما يشبك",
    
    # Wrong numbers
    "الرقم خطأ", "الرقم لا يخص", "لا يخص العميل", "رقم غلط", "لايخص", "غير صحيح",
    
    # Others
    "ما عندي", "ما يبي", "ما يقدر", "مقدر اسدد", "تنكر", "أنكر", "هرب", "خروج نهائي", "سجن", "مسجون"
]


class TargetCustomersModule:
    CLASS_COL    = "العملاء المستهدفة"
    CATEGORY_COL = "تصنيف الاستهداف"
    PRIORITY_COL = "أولوية التحصيل"
    REASON_COL   = "سبب التصنيف"

    def run(
        self,
        portfolio: pl.DataFrame,
        promise: pl.DataFrame = None,
        maharah: pl.DataFrame = None,
        **kwargs,
    ) -> Dict:
        _log.info("▶ بدء تحديد العملاء المستهدفة (تطبيق الفلترة المزدوجة المعززة)")

        id_col = next((c for c in ["رقم الهوية", "الهوية"] if c in portfolio.columns), None)
        if id_col:
            portfolio = portfolio.with_columns(
                (pl.lit(1.0) / pl.col(id_col).count().over(id_col).cast(pl.Float64)).alias("عدد العملاء")
            )
        else:
            portfolio = portfolio.with_columns(pl.lit(1.0).alias("عدد العملاء"))

        df = portfolio.clone()
        df = self._classify(df)

        positive_df = df.filter(pl.col(self.CLASS_COL) == POSITIVE)

        piv_sup = self._build_pivot(df, "المشرف")
        collector = next((c for c in ["المحصل", "الموظف"] if c in df.columns), "")
        piv_col   = self._build_pivot(df, collector) if collector else pl.DataFrame()

        total = len(df)
        pos_count = df.filter(pl.col(self.CLASS_COL) == POSITIVE).height
        neg_count = df.filter(pl.col(self.CLASS_COL) == NEGATIVE).height

        category_counts = {}
        if pos_count > 0:
            cat_df = positive_df.group_by(self.CATEGORY_COL).len()
            for r in cat_df.iter_rows(named=True):
                key = r[self.CATEGORY_COL]
                if key is None:
                    key = "مستهدف (أخرى/حالة نظام)"
                category_counts[key] = int(r["len"])

        stats = {
            "إجمالي العملاء":    total,
            "مستهدف":            pos_count,
            "غير مستهدف":        neg_count,
            "نسبة المستهدفين %": round(pos_count / total * 100, 1) if total else 0.0,
        }
        stats.update(category_counts)

        return {
            "data":             df,
            "positive_data":    positive_df,
            "pivot_supervisor": piv_sup,
            "pivot_collector":  piv_col,
            "stats":            stats,
        }

    def _normalize_text(self, text_col: str) -> pl.Expr:
        return (
            pl.col(text_col)
            .fill_null("")
            .cast(pl.String)
            .str.strip_chars()
            .str.to_lowercase()
            .str.replace_all("أ", "ا")
            .str.replace_all("إ", "ا")
            .str.replace_all("آ", "ا")
            .str.replace_all("ة", "ه")
            .str.replace_all("ى", "ي")
            .str.replace_all("ض", "ظ")
        )

    def _classify(self, df: pl.DataFrame) -> pl.DataFrame:
        note_col = next((c for c in ["المتابعة", "الملاحظة", "الملاحظات", "ملاحظة"] if c in df.columns), None)
        main_col = next((c for c in ["حالة المتابعة الرئيسية", "الحالة الرئيسية", "الحالة"] if c in df.columns), None)
        sub_col  = next((c for c in ["حالة المتابعة الفرعية", "الحالة الفرعية"] if c in df.columns), None)

        if not note_col:
            _log.warning("لم يتم العثور على عمود المتابعة!")
            return df.with_columns([
                pl.lit(NEGATIVE).alias(self.CLASS_COL),
                pl.lit("❌ غير مستهدف").alias(self.CATEGORY_COL),
                pl.lit("لا يوجد عمود متابعة").alias(self.REASON_COL),
                pl.lit(2).cast(pl.Int32).alias(self.PRIORITY_COL),
            ])

        note_expr = self._normalize_text(note_col)
        main_expr = self._normalize_text(main_col) if main_col else pl.lit("")
        sub_expr  = self._normalize_text(sub_col) if sub_col else pl.lit("")

        import re
        def _to_regex(kws):
            return "|".join(re.escape(kw.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي").replace("ض", "ظ")) for kw in kws)

        NEGATED_PAYMENT_PHRASES = [
            "لا سداد", "لن سداد", "مش سداد", "ما سداد", "مو سداد", "غير سداد", "رفض سداد", "رافض سداد",
            "لا يسدد", "لن يسدد", "مش يسدد", "ما يسدد", "مو يسدد", "غير يسدد", "رفض يسدد", "رافض يسدد", "مايسدد", "لايسدد",
            "لا هيسدد", "لن هيسدد", "مش هيسدد", "ما هيسدد", "مو هيسدد",
            "لا دفع", "لن دفع", "مش دفع", "ما دفع", "مو دفع", "غير دفع", "رفض دفع", "رافض دفع",
            "لا تحويل", "لن تحويل", "مش تحويل", "ما تحويل", "مو تحويل", "غير تحويل", "رفض تحويل", "رافض تحويل",
            "ما بيسدد", "مابيسدد", "ما بسدد", "مابسدد", "ما راح يسدد", "ماراح يسدد", "ما رح يسدد", "مارح يسدد",
            "ما راح اسدد", "ماراح اسدد", "ما رح اسدد", "مارح اسدد", "ما اسدد", "مااسدد",
            "ما ني مسدد", "ماني مسدد", "مو مسدد", "مهو مسدد", "غير مسدد",
            "ما يقدر يسدد", "مايقدر يسدد", "ما يقدر بسدد", "مقدر يسدد", "مقدر اسدد", "ما اقدر اسدد", "مااقدر اسدد",
            "ما يبي يسدد", "مايبي يسدد", "ما يبي يدفع",
            "ما يدفع", "مايدفع", "لا يدفع", "لايدفع", "لن يدفع", "لم يدفع",
            "ما راح يدفع", "ماراح يدفع", "ما رح يدفع", "مارح يدفع",
            "ماني دافع", "مو دافع",
            "ما عنده يسدد", "ماعنده يسدد", "ما عنده حق",
            "رافض السداد", "رفض السداد", "رافض يدفع", "رافض يسدد", "يرفض السداد", "يرفض يسدد",
            "رافضين السداد", "رافضين سداد", "رافضين", "ما معه فلوس", "مامعه فلوس", "ما معاه فلوس", "طفران", "طفاران", "شؤون قانونية", "شؤون قانونيه"
        ]
        neg_re = _to_regex(NEGATED_PAYMENT_PHRASES)
        
        # Apply Negation Masking BEFORE searching for positive keywords!
        # This prevents "ما بيسدد" from falsely triggering "بيسدد"
        masked_note_expr = note_expr.str.replace_all(neg_re, " REJECTED_PAYMENT ")

        # ── 1. الفلتر الأولي (الحالة الرئيسية أو الفرعية المسموحة) ─────────────
        primary_main_re = _to_regex(PRIMARY_MAIN_STATUSES)
        primary_sub_re = _to_regex(PRIMARY_SUB_STATUSES)
        has_primary_status = (
            main_expr.str.contains(primary_main_re, literal=False) | 
            sub_expr.str.contains(primary_sub_re, literal=False)
        )

        # ── 2. فحص كولوم كامل السداد (مستبعد فوراً لأنه سدد وخلاص) ──────────────
        fully_paid_re = _to_regex(FULLY_PAID_KEYWORDS)
        has_fully_paid = (
            note_expr.str.contains(fully_paid_re, literal=False) | 
            main_expr.str.contains(fully_paid_re, literal=False) | 
            sub_expr.str.contains(fully_paid_re, literal=False)
        )

        # ── 3. فحص الكلمات السلبية والمستبعدة ────────────────────────────────
        disqualify_re = _to_regex(DISQUALIFY_KEYWORDS)
        has_disqualify = note_expr.str.contains(disqualify_re, literal=False)
        extracted_disqualify = note_expr.str.extract(f"({disqualify_re})", 1)
        
        disqualify_reason_expr = (
            pl.when(has_disqualify)
            .then(pl.concat_str([pl.lit("مستبعد: "), extracted_disqualify.fill_null("")]))
            .otherwise(pl.lit("عدم تواصل / استبعاد"))
        )

        # ── 4. فحص الفئات الإيجابية الست ─────────────────────────────────────
        category_expr_list = []
        has_any_positive = pl.lit(False)

        for cat_name, kw_list in TARGET_CATEGORIES.items():
            cat_re = _to_regex(kw_list)
            cat_match = masked_note_expr.str.contains(cat_re, literal=False)
            has_any_positive = has_any_positive | cat_match
            category_expr_list.append(
                pl.when(cat_match).then(pl.lit(cat_name)).otherwise(pl.lit(None))
            )

        pos_category_expr = pl.coalesce(category_expr_list)

        # ── 5. قاعدة الاستهداف الصارمة ───────────────────────────────────────
        # 1- يجب أن تكون هناك كلمة إيجابية صريحة (has_any_positive = True)
        # 2- الأولوية دائما للكلمات السلبية (has_disqualify = False)
        # 3- لم يتم سداد المديونية بالكامل
        is_targeted = has_primary_status & has_any_positive & (~has_fully_paid) & (~has_disqualify)

        class_expr = pl.when(is_targeted).then(pl.lit(POSITIVE)).otherwise(pl.lit(NEGATIVE))
        
        category_result_expr = (
            pl.when(is_targeted)
            .then(pos_category_expr)
            .otherwise(pl.lit("❌ غير مستهدف"))
        )

        reason_result_expr = (
            pl.when(has_fully_paid)
            .then(pl.lit("✅ تم سداد كامل المديونية"))
            .otherwise(
                pl.when(is_targeted)
                .then(pl.lit("كلمة إيجابية صريحة بالسداد / منتظم"))
                .otherwise(
                    pl.when(has_disqualify)
                    .then(disqualify_reason_expr)
                    .otherwise(pl.lit("لا تتوفر عبارات سداد إيجابية"))
                )
            )
        )

        df = df.with_columns([
            class_expr.alias(self.CLASS_COL),
            category_result_expr.alias(self.CATEGORY_COL),
            reason_result_expr.alias(self.REASON_COL),
            pl.when(is_targeted).then(pl.lit(1)).otherwise(pl.lit(2)).cast(pl.Int32).alias(self.PRIORITY_COL)
        ])

        return df

    def _build_pivot(self, df: pl.DataFrame, group_col: str) -> pl.DataFrame:
        if not group_col or group_col not in df.columns:
            return pl.DataFrame()

        try:
            pivot = (
                df.group_by([group_col, self.CLASS_COL])
                .len()
                .pivot(on=self.CLASS_COL, index=group_col, values="len")
                .fill_null(0)
            )
            for col in [POSITIVE, NEGATIVE]:
                if col not in pivot.columns:
                    pivot = pivot.with_columns(pl.lit(0).alias(col))
            pivot = pivot.with_columns(
                (pl.col(POSITIVE) + pl.col(NEGATIVE)).alias("الإجمالي")
            )
            return pivot
        except Exception as e:
            _log.warning("فشل إنشاء جدول المحور لـ %s: %s", group_col, e)
            return pl.DataFrame()
