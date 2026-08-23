"""
modules/module1_errors.py
─────────────────────────
Module 1 — اخطاء النظام (System Errors) using Polars.

يضيف الأعمدة التالية:
  • الخطأ        — اسم/أسماء الأخطاء المكتشفة مطابقاً لكتيب الشركة (مفصولة بـ |)
  • تصحيح الخطأ — الإجراء الصحيح المقابل لكل خطأ مطابقاً لكتيب الشركة
  • تاريخ وعد السداد — التاريخ المجلوب من ملف الوعود
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import polars as pl

from core.utils import get_today, parse_date

_log = logging.getLogger("Module1_Errors")

# ── الثوابت المعتمدة بكتيب الشركة ─────────────────────────────────────────
BAD_FOLLOWUP_TEXT   = "تحديث على نفس الحالة"
SEP = " | "   # فاصل الأخطاء المتعددة


def _find_col(df: pl.DataFrame, candidates: list) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _clean_float(col_name: str) -> pl.Expr:
    return (
        pl.col(col_name)
        .cast(pl.String, strict=False)
        .str.replace_all(",", "", literal=True)
        .str.replace_all(r"[^\d\.-]", "", literal=False)
        .str.strip_chars()
        .cast(pl.Float64, strict=False)
        .fill_null(0.0)
    )


class SystemErrorsModule:

    def run(
        self,
        portfolio: pl.DataFrame,
        promise: Optional[pl.DataFrame] = None,
        **kwargs,
    ) -> Dict:
        # إضافة كولوم عدد العملاء = 1 / countif(رقم الهوية)
        id_col = next((c for c in ["رقم الهوية", "الهوية"] if c in portfolio.columns), None)
        if id_col:
            portfolio = portfolio.with_columns(
                (pl.lit(1.0) / pl.col(id_col).count().over(id_col).cast(pl.Float64)).alias("عدد العملاء")
            )
        else:
            portfolio = portfolio.with_columns(pl.lit(1.0).alias("عدد العملاء"))

        # 1. إثراء بتاريخ وعد السداد
        df = self._enrich_with_promise(portfolio, promise)

        # 2. حساب القواعد
        rules: List[Tuple] = []

        # رقم تواصل رئيسي للعميل أو خطأ
        r1 = self._rule1_primary_id(df)
        if r1 is not None:
            rules.append((r1, "رقم تواصل رئيسي للعميل أو خطأ", "وضع رقم تواصل رئيسي لكل عميل"))

        # عدم كتابة ملاحظة واضحة
        r2 = self._rule2_followup(df)
        if r2 is not None:
            rules.append((r2, "عدم كتابة ملاحظة واضحة", "يجب ان تكون الافادة كافية وتشرح المكالمة"))

        # السداد والحالة
        rules.extend(self._rule3_payment_status(df))

        # عدم تحديث تاريخ أو مبلغ الوعد
        r4 = self._rule4_promise_date(df)
        if r4 is not None:
            rules.append((r4, "عدم تحديث تاريخ أو مبلغ الوعد", "تحديث تاريخ الوعد عند كل مكالمة قادمة للعميل"))

        # 3. بناء عمودَي الأخطاء
        df = self._build_error_columns(df, rules)

        # 4. الاحتفاظ بـ تاريخ وعد السداد في التقرير
        if "_promise_date_latest" in df.columns:
            df = df.rename({"_promise_date_latest": "تاريخ وعد السداد"})
        else:
            df = df.with_columns(pl.lit("").alias("تاريخ وعد السداد"))

        # 5. إحصائيات
        total     = len(df)
        has_error = df.filter(
            (pl.col("الخطأ").is_not_null()) & (pl.col("الخطأ") != "")
        ).height

        def _count_err(label: str) -> int:
            return df.filter(pl.col("الخطأ").str.contains(label, literal=True)).height

        stats = {
            "إجمالي العملاء":              total,
            "عملاء بأخطاء":                has_error,
            "عملاء بدون أخطاء":            total - has_error,
            "نسبة الأخطاء %":              round(has_error / total * 100, 1) if total else 0.0,
            
            # الربط مع الـ KPI Cards لوحة القيادة القديمة لعدم حدوث أي كسر للمؤشرات
            "خطأ الرقم الرئيسي":           _count_err("رقم تواصل رئيسي للعميل أو خطأ"),
            "خطأ الإفادة":                 _count_err("عدم كتابة ملاحظة واضحة"),
            "خطأ الوعد":                   _count_err("عدم تحديث تاريخ أو مبلغ الوعد"),
            "خطأ الحالة":                  (
                _count_err("سداد جزئي ولا يوجد دفعه للعميل") +
                _count_err("تم السداد والعميل مازال سداد جزئي") +
                _count_err("تم السداد والعميل سدد المديونية الخاصة به كاملة او بخصم") +
                _count_err("خطأ توثيق السداد") +
                _count_err("خطأ توافق الحالة مع السداد")
            )
        }

        return {"data": df, "stats": stats}

    # ── مساعد بناء عمودَي الخطأ والتصحيح ───────────────────────────────

    def _build_error_columns(
        self,
        df: pl.DataFrame,
        rules: List[Tuple],
    ) -> pl.DataFrame:
        if not rules:
            return df.with_columns(
                pl.lit("").alias("الخطأ"),
                pl.lit("").alias("تصحيح الخطأ"),
            )

        # ── نهج fully vectorized: كل rule تنتج String أو null ─────────────
        # ثم pl.concat_str بـ ignore_nulls=True تجمع القيم غير الفارغة فقط
        # لا map_elements، لا Python loops — يعمل بسرعة C على أي حجم داتا
        error_parts = [
            pl.when(mask).then(pl.lit(name)).otherwise(pl.lit(None))
            for mask, name, _ in rules
        ]
        fix_parts = [
            pl.when(mask).then(pl.lit(fix)).otherwise(pl.lit(None))
            for mask, _, fix in rules
        ]

        return df.with_columns([
            pl.concat_str(error_parts, separator=SEP, ignore_nulls=True).alias("الخطأ"),
            pl.concat_str(fix_parts,   separator=SEP, ignore_nulls=True).alias("تصحيح الخطأ"),
        ])


    # ── القواعد ──────────────────────────────────────────────────────────

    def _rule1_primary_id(self, df: pl.DataFrame) -> Optional[pl.Expr]:
        """رقم تواصل رئيسي للعميل أو خطأ."""
        col = _find_col(df, ["الرقم الرئيسي", "رقم الحساب الرئيسي", "الرقم_الرئيسي"])
        if col is None:
            return None
        return (pl.col(col).is_null()) | (
            pl.col(col).cast(pl.String, strict=False).str.strip_chars() == ""
        )

    def _rule2_followup(self, df: pl.DataFrame) -> Optional[pl.Expr]:
        """عدم كتابة ملاحظة واضحة (فارغة، أو لا معنى لها، أو تحديث على نفس الحالة)."""
        col = _find_col(df, ["الملاحظة", "الملاحظات", "ملاحظة", "المتابعة", "آخر متابعة"])
        if col is None:
            return None

        # القيم التافهة — Polars vectorized (لا map_elements)
        GENERIC_NOTES = [
            "لا يوجد", "بدون", "-", ".", "..", "...", "لايوجد",
            "تم التواصل", "تواصل", "ok", "okay", "n/a", "na", "",
        ]
        note_expr = (
            pl.col(col)
            .cast(pl.String, strict=False)
            .str.strip_chars()
            .str.to_lowercase()
        )

        # فارغة أو null
        is_empty_note = pl.col(col).is_null() | (note_expr == "")

        # نص تافه من القائمة
        is_generic = note_expr.is_in(GENERIC_NOTES)

        # نص "تحديث على نفس الحالة"
        is_bad_text = (
            pl.col(col)
            .cast(pl.String, strict=False)
            .str.strip_chars()
            .str.contains(BAD_FOLLOWUP_TEXT, literal=True)
        )

        return is_empty_note | is_generic | is_bad_text

    def _rule3_payment_status(self, df: pl.DataFrame) -> List[Tuple]:
        """سداد العميل مع حالته الرئيسية."""
        status_col = _find_col(df, ["الحالة الرئيسية"])
        paid_col   = _find_col(df, ["السدادات الموثقة", "مبلغ السداد", "السداد"])
        remain_col = _find_col(df, ["متبقي سداد موثق", "متبقي سداد العقد", "المتبقي"])

        if not status_col:
            return []

        status = pl.col(status_col).cast(pl.String, strict=False).str.strip_chars()
        is_fully_paid = status.is_in([
            "تم سداد", "تم السداد", "مسدد", "سداد كامل", "مسدد بالكامل", 
            "سداد كامل المديونية", "كامل المديونية", "paid", "full payment"
        ])
        is_partial = status.is_in([
            "سداد جزئي", "جزئي", "سداد جزئي "
        ])

        paid_amount = _clean_float(paid_col) if paid_col else pl.lit(0.0)
        no_paid     = paid_amount <= 0.0
        remain      = _clean_float(remain_col) if remain_col else pl.lit(0.0)

        return [
            # تم السداد مع وجود متبقي مديونية
            (
                is_fully_paid & (remain > 0.0),
                "تم السداد والعميل سدد المديونية الخاصة به كاملة او بخصم",
                "يجب مراجعة حالة العميل أو قيمة متبقي السداد.",
            ),
            # تم السداد ولا يوجد سداد موثق
            (
                is_fully_paid & no_paid,
                "خطأ توثيق السداد",
                "يجب توثيق السداد أو تعديل الحالة.",
            ),
            # سداد جزئي ولا يوجد دفعات
            (
                is_partial & no_paid,
                "سداد جزئي ولا يوجد دفعه للعميل",
                "الحالة: العميل واعد بالسداد",
            ),
            # متبقي صفر والعميل ما زال سداد جزئي
            (
                is_partial & (remain <= 0.0) & (~no_paid),
                "تم السداد والعميل مازال سداد جزئي",
                "الحالة: تم السداد",
            ),
            # سداد بدون توافق الحالة
            (
                (~no_paid) & (~is_fully_paid) & (~is_partial),
                "خطأ توافق الحالة مع السداد",
                "يجب تعديل الحالة الرئيسية لتتوافق مع السداد الموثق.",
            ),
        ]

    def _rule4_promise_date(self, df: pl.DataFrame) -> Optional[pl.Expr]:
        """عدم تحديث تاريخ أو مبلغ الوعد — Polars vectorized."""
        if "_promise_date_latest" not in df.columns:
            return None

        today      = get_today()
        status_col = _find_col(df, ["الحالة الرئيسية"])

        if status_col:
            status = pl.col(status_col).cast(pl.String, strict=False).str.strip_chars()
            is_fully_paid = status.is_in([
                "تم سداد", "تم السداد", "مسدد", "سداد كامل", "مسدد بالكامل",
                "سداد كامل المديونية", "كامل المديونية", "paid", "full payment"
            ])
        else:
            is_fully_paid = pl.lit(False)

        # تحويل النص إلى تاريخ بشكل vectorized ثم مقارنة — لا map_elements
        today_lit = pl.lit(today)
        date_expr = (
            pl.col("_promise_date_latest")
            .cast(pl.String, strict=False)
            .str.strip_chars()
            .str.replace(r"\s+.*$", "")   # حذف مكوّن الوقت إن وُجد
        )

        # null أو فارغ → منتهي الصلاحية
        is_null_date = pl.col("_promise_date_latest").is_null() | (date_expr == "")

        # محاولة parse بأكثر الصيغ شيوعاً (m/d/Y أولاً لمطابقة البيانات الفعلية)
        parsed = (
            date_expr.str.to_date("%m/%d/%Y", strict=False)
            .fill_null(date_expr.str.to_date("%Y-%m-%d", strict=False))
            .fill_null(date_expr.str.to_date("%d/%m/%Y", strict=False))
            .fill_null(date_expr.str.to_date("%Y/%m/%d", strict=False))
            .fill_null(date_expr.str.to_date("%d-%m-%Y", strict=False))
            .fill_null(date_expr.str.to_date("%m-%d-%Y", strict=False))
        )
        # إذا فشل كل parse → null → نعتبره منتهياً
        is_expired_parsed = parsed.is_null() | (parsed < today_lit)

        expired_mask = is_null_date | is_expired_parsed

        return expired_mask & (~is_fully_paid)

    # ── إثراء بيانات وعد السداد ──────────────────────────────────────────

    def _enrich_with_promise(
        self, df: pl.DataFrame, promise: Optional[pl.DataFrame]
    ) -> pl.DataFrame:
        """VLOOKUP: تاريخ وعد السداد من ملف الوعود بالمطابقة على رقم المديونية."""
        if promise is None or len(promise) == 0:
            return df.with_columns(pl.lit("").alias("_promise_date_latest"))

        join_key_p  = _find_col(df,      ["رقم المديونية", "رقم الحساب"])
        join_key_pr = _find_col(promise, ["رقم المديونية", "رقم الحساب"])
        date_col    = _find_col(promise, ["تاريخ وعد السداد", "وعد السداد"])

        if not join_key_p or not join_key_pr or not date_col:
            _log.warning("لم يتم العثور على أعمدة المطابقة — سيتم تجاهل القاعدة 4.")
            return df.with_columns(pl.lit("").alias("_promise_date_latest"))

        try:
            promise_clean = (
                promise
                .filter(
                    pl.col(join_key_pr).is_not_null()
                    & (pl.col(join_key_pr).cast(pl.String, strict=False).str.strip_chars() != "")
                )
                .sort(date_col, descending=True)
                .unique(subset=[join_key_pr], keep="first")
                .select([
                    pl.col(join_key_pr)
                      .cast(pl.String, strict=False)
                      .str.strip_chars()
                      .alias("_pk"),
                    pl.col(date_col)
                      .cast(pl.String, strict=False)
                      .alias("_promise_date_latest"),
                ])
            )

            df_keyed = df.with_columns(
                pl.col(join_key_p)
                  .cast(pl.String, strict=False)
                  .str.strip_chars()
                  .alias("_pk")
            )

            result = df_keyed.join(promise_clean, on="_pk", how="left").drop("_pk")

            if "_promise_date_latest" not in result.columns:
                result = result.with_columns(pl.lit("").alias("_promise_date_latest"))
            else:
                result = result.with_columns(
                    pl.col("_promise_date_latest").fill_null("")
                )
            return result

        except Exception as exc:
            _log.warning("فشل إثراء وعد السداد: %s", exc)
            return df.with_columns(pl.lit("").alias("_promise_date_latest"))
