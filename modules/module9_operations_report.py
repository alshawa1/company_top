import logging
import re
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
import polars as pl

_log = logging.getLogger("STC_OPS")

_ID_COLS           = ["رقم الهوية", "الهوية", "الرقم الرئيسي", "رقم العميل", "رقم الحساب", "ID"]
_BALANCE_COLS      = ["متبقي سداد موثق", "متبقي السداد الموثق", "متبقي سداد العقد", "مبلغ المديونية", "المديونية", "Balance"]
_PAID_COLS         = ["السدادات الموثقة", "سدادات العقود", "مبلغ السداد", "Paid"]
_PORTFOLIO_COLS     = ["المحافظ", "المحفظة", "اسم المحفظة", "Portfolio"]
_SUPERVISOR_COLS    = ["المشرف", "اسم المشرف", "Supervisor"]
_COLLECTOR_COLS     = ["المحصل", "اسم المحصل", "الموظف", "محصل", "Collector"]
_USER_COLS          = ["اسم المستخدم", "اليوزر", "User", "user", "المستخدم"]
_FOLLOWUP_DATE_COLS = ["تاريخ المتابعة", "تاريخ اخر متابعة", "آخر متابعة للعميل", "المتابعة", "Followup Date"]
_MAIN_STATUS_COLS   = ["الحالة الرئيسية", "الحالة", "Main Status"]
_SUB_STATUS_COLS    = ["الحالة الفرعية", "Sub Status"]


def _detect(df: pl.DataFrame, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    for c in df.columns:
        for cand in candidates:
            if cand in c or c in cand:
                return c
    return None


def _clean_float(series: pl.Series) -> pl.Series:
    return (
        series
        .cast(pl.String, strict=False)
        .str.replace_all(",", "", literal=True)
        .str.replace_all(r"[^\d\.-]", "", literal=False)
        .str.strip_chars()
        .cast(pl.Float64, strict=False)
        .fill_null(0.0)
    )


_RE_US_DATE  = re.compile(r"^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})")
_RE_ISO_DATE = re.compile(r"^(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})")


def _normalize_date_val(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, (datetime, date)):
        return val.strftime("%Y-%m-%d")
    v = str(val).strip()
    if not v or v in ("-", "None", "null"):
        return ""

    # 1. ISO format: YYYY-MM-DD or YYYY/MM/DD
    m2 = _RE_ISO_DATE.match(v)
    if m2:
        y, m, d = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        return f"{y:04d}-{m:02d}-{d:02d}"

    # 2. DD/MM/YYYY or MM/DD/YYYY (Standard Arabic / Middle East format is DD/MM/YYYY)
    m = _RE_US_DATE.match(v)
    if m:
        p1, p2, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if p1 > 12:
            d, m = p1, p2
        elif p2 > 12:
            d, m = p2, p1
        else:
            # Arabic files use DD/MM/YYYY
            d, m = p1, p2
        return f"{y:04d}-{m:02d}-{d:02d}"

    return v[:10]


class OperationsReportModule:
    """
    نظام تقارير العمليات الاحترافي (Operations Reporting System - Reports Center)
    يدعم إنشاء تقارير مستقلة بالكامل:
    - 📅 Daily Report (تقرير يومي)
    - 🗓 Weekly Report (تقرير أسبوعي)
    - 📆 Monthly Report (تقرير شهري)
    مع فلترة مخصصة وحساب دقيق للمؤشرات حسب نوع التقرير والفترة الزمنية المختارة دون تعديل البيانات الأصلية.
    """

    @staticmethod
    def get_filter_options(portfolio: pl.DataFrame) -> Dict[str, List[str]]:
        """يستخرج خيارات الفلاتر المتاحة من الملف لتغذية واجهة المستخدم"""
        if portfolio is None or len(portfolio) == 0:
            return {}

        def _get_unique(col_name: Optional[str]) -> List[str]:
            if not col_name or col_name not in portfolio.columns:
                return []
            s = (
                portfolio[col_name]
                .cast(pl.String, strict=False)
                .str.strip_chars()
                .drop_nulls()
                .unique()
                .sort()
            )
            result = [v for v in s.to_list() if v and str(v).strip() != ""]
            return result

        return {
            "supervisors": _get_unique(_detect(portfolio, _SUPERVISOR_COLS)),
            "collectors": _get_unique(_detect(portfolio, _COLLECTOR_COLS)),
            "portfolios": _get_unique(_detect(portfolio, _PORTFOLIO_COLS)),
            "main_statuses": _get_unique(_detect(portfolio, _MAIN_STATUS_COLS)),
            "sub_statuses": _get_unique(_detect(portfolio, _SUB_STATUS_COLS)),
        }

    def run(
        self,
        portfolio: pl.DataFrame,
        payments: Optional[pl.DataFrame] = None,
        report_mode: str = "daily",  # "daily", "weekly", "monthly"
        target_date: Optional[str] = None,
        target_dates: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        month: Optional[int] = None,
        year: Optional[int] = None,
        supervisors: Optional[List[str]] = None,
        collectors: Optional[List[str]] = None,
        portfolios: Optional[List[str]] = None,
        main_statuses: Optional[List[str]] = None,
        sub_statuses: Optional[List[str]] = None,
        supervisor_targets: Optional[Dict] = None,
        **kwargs,
    ) -> Dict[str, Any]:

        if portfolio is None or len(portfolio) == 0:
            raise ValueError("ملف المحفظة فارغ أو غير ممرر")

        # 1. كشف الأعمدة الأساسية
        id_col        = _detect(portfolio, _ID_COLS)
        bal_col       = _detect(portfolio, _BALANCE_COLS)
        paid_col      = _detect(portfolio, _PAID_COLS)
        prt_col       = _detect(portfolio, _PORTFOLIO_COLS)
        sup_col       = _detect(portfolio, _SUPERVISOR_COLS)
        col_col       = _detect(portfolio, _COLLECTOR_COLS)
        usr_col       = _detect(portfolio, _USER_COLS)
        followup_col  = _detect(portfolio, _FOLLOWUP_DATE_COLS)
        main_stat_col = _detect(portfolio, _MAIN_STATUS_COLS)
        sub_stat_col  = _detect(portfolio, _SUB_STATUS_COLS)

        if not id_col or not prt_col or not col_col:
            raise ValueError("لم يتم العثور على الأعمدة الأساسية للمحفظة (الهوية، المحفظة، المحصل)")

        df_work = portfolio.clone()

        # 2. تطبيق الفلاتر المخصصة من المستخدم (إن وجدت)
        if supervisors and sup_col and sup_col in df_work.columns:
            df_work = df_work.filter(pl.col(sup_col).cast(pl.String).str.strip_chars().is_in(supervisors))
        if collectors and col_col and col_col in df_work.columns:
            df_work = df_work.filter(pl.col(col_col).cast(pl.String).str.strip_chars().is_in(collectors))
        if portfolios and prt_col and prt_col in df_work.columns:
            df_work = df_work.filter(pl.col(prt_col).cast(pl.String).str.strip_chars().is_in(portfolios))
        if main_statuses and main_stat_col and main_stat_col in df_work.columns:
            df_work = df_work.filter(pl.col(main_stat_col).cast(pl.String).str.strip_chars().is_in(main_statuses))
        if sub_statuses and sub_stat_col and sub_stat_col in df_work.columns:
            df_work = df_work.filter(pl.col(sub_stat_col).cast(pl.String).str.strip_chars().is_in(sub_statuses))

        if len(df_work) == 0:
            raise ValueError("لا توجد بيانات مطابقة للفلاتر المحددة!")

        # 3. تحديد نوع التقرير والفترة الزمنية والتغطية
        today_obj = date.today()
        report_mode = report_mode.lower().strip()
        
        report_title = ""
        report_period_str = ""

        # تحويل تاريخ المتابعة لـ String YYYY-MM-DD موحد
        if followup_col and followup_col in df_work.columns:
            raw_dates = df_work[followup_col].to_list()
            clean_dates_list = [_normalize_date_val(d) for d in raw_dates]
            followup_series_str = pl.Series(clean_dates_list)
        else:
            followup_series_str = pl.Series([today_obj.strftime("%Y-%m-%d")] * len(df_work))

        # حساب التغطية بناءً على التواريخ ونوع التقرير
        if target_dates and len(target_dates) > 0:
            clean_dates = [str(d).strip() for d in target_dates if d]
            report_title = "📅 تقرير الأيام المحددة"
            report_period_str = f"التواريخ المحددة: {', '.join(clean_dates)}"
            is_covered_expr = followup_series_str.is_in(clean_dates)
        elif report_mode == "daily":
            if not target_date:
                non_null_dates = followup_series_str.filter(followup_series_str.str.contains(r"^\d{4}-\d{2}-\d{2}$")).to_list()
                target_date_str = max(non_null_dates) if non_null_dates else today_obj.strftime("%Y-%m-%d")
            else:
                target_date_str = _normalize_date_val(target_date)

            report_title = "📅 التقرير اليومي (Daily Report)"
            report_period_str = f"تاريخ التقرير: {target_date_str}"
            is_covered_expr = (followup_series_str == target_date_str) | (followup_series_str.str.contains(target_date_str))

        elif report_mode == "weekly":
            if not start_date or not end_date:
                e_dt = today_obj
                s_dt = today_obj - timedelta(days=6)
                start_date_str = s_dt.strftime("%Y-%m-%d")
                end_date_str = e_dt.strftime("%Y-%m-%d")
            else:
                start_date_str = _normalize_date_val(start_date)
                end_date_str = _normalize_date_val(end_date)

            report_title = "🗓 التقرير الأسبوعي (Weekly Report)"
            report_period_str = f"الفترة الأسبوعية: من {start_date_str} إلى {end_date_str}"
            is_covered_expr = (followup_series_str >= start_date_str) & (followup_series_str <= end_date_str)

        elif report_mode == "monthly":
            m_val = month if month else today_obj.month
            y_val = year if year else today_obj.year
            month_prefix = f"{y_val:04d}-{m_val:02d}"

            report_title = "📆 التقرير الشهري (Monthly Report)"
            report_period_str = f"فترة الشهر: {month_prefix} ({m_val}/{y_val})"
            is_covered_expr = followup_series_str.str.starts_with(month_prefix)
        else:
            report_title = "📊 تقرير العمليات الشامل"
            report_period_str = f"تاريخ التقرير: {today_obj.strftime('%Y-%m-%d')}"
            is_covered_expr = pl.Series([True] * len(df_work))

        # 4. مبالغ المديونية والسداد
        bal_series = _clean_float(df_work[bal_col]) if bal_col and bal_col in df_work.columns else pl.Series([0.0] * len(df_work))
        paid_series = _clean_float(df_work[paid_col]) if paid_col and paid_col in df_work.columns else pl.Series([0.0] * len(df_work))

        # معالجة ملف السدادات الإضافية إن وجد (حساب التحصيل مباشرة من كولوم مبلغ السداد)
        payments_sum_map = {}
        payments_cnt_map = {}
        if payments is not None and len(payments) > 0:
            pmt_id_col  = _detect(payments, ["رقم الهوية", "الهوية", "رقم الحساب", "الرقم الرئيسي", "ID"])
            pmt_amt_col = _detect(payments, ["مبلغ السداد", "مبلغ السداد الموثق", "السدادات الموثقة", "المبلغ", "Amount"])
            pmt_dt_col  = _detect(payments, ["تاريخ السداد", "تاريخ الحركة", "تاريخ العملية", "التاريخ", "Date", "payment_date"])

            if pmt_id_col and pmt_amt_col:
                pmt_clean = payments.with_columns([
                    pl.col(pmt_id_col).cast(pl.String).str.replace(r"\.0$", "", literal=False).str.strip_chars(),
                    _clean_float(payments[pmt_amt_col]).alias("clean_pmt_amt")
                ])

                # تصفية ملف السدادات حسُب الفترة الزمنية للتقرير إن وجد عمود التاريخ
                if pmt_dt_col and pmt_dt_col in pmt_clean.columns:
                    raw_pmt_dates = pmt_clean[pmt_dt_col].to_list()
                    clean_pmt_dates = [_normalize_date_val(d) for d in raw_pmt_dates]
                    pmt_clean = pmt_clean.with_columns(pl.Series("pmt_date_str", clean_pmt_dates))

                    if target_dates and len(target_dates) > 0:
                        pmt_clean = pmt_clean.filter(pl.col("pmt_date_str").is_in(clean_dates))
                    elif report_mode == "daily" and 'target_date_str' in locals():
                        pmt_clean = pmt_clean.filter(pl.col("pmt_date_str") == target_date_str)
                    elif report_mode == "weekly" and 'start_date_str' in locals() and 'end_date_str' in locals():
                        pmt_clean = pmt_clean.filter((pl.col("pmt_date_str") >= start_date_str) & (pl.col("pmt_date_str") <= end_date_str))
                    elif report_mode == "monthly" and 'month_prefix' in locals():
                        pmt_clean = pmt_clean.filter(pl.col("pmt_date_str").str.starts_with(month_prefix))

                grp_pmt = pmt_clean.group_by(pmt_id_col).agg([
                    pl.col("clean_pmt_amt").sum().alias("total_pmt"),
                    pl.len().alias("count_pmt")
                ])
                for r in grp_pmt.iter_rows(named=True):
                    payments_sum_map[str(r[pmt_id_col])] = float(r["total_pmt"])
                    payments_cnt_map[str(r[pmt_id_col])] = int(r["count_pmt"])

        if payments_sum_map:
            ids_str = df_work[id_col].cast(pl.String).str.replace(r"\.0$", "", literal=False).str.strip_chars().to_list()
            added_pmts = [payments_sum_map.get(i, 0.0) for i in ids_str]
            added_cnts = [payments_cnt_map.get(i, 0) for i in ids_str]
            # اعتماد مبلغ السداد مباشرة من ملف السدادات المرفوع
            total_paid_expr = pl.Series(added_pmts)
            count_paid_expr = pl.Series(added_cnts)
        else:
            total_paid_expr = paid_series
            count_paid_expr = (paid_series > 0).cast(pl.Int64)

        # إضافة كولومات التحليل الشامل (التواصل / عدم التواصل / لايرد / مغلق)
        note_str_col = followup_col if followup_col in df_work.columns else (main_stat_col or col_col)
        norm_note_expr = df_work[note_str_col].cast(pl.String, strict=False).fill_null("").str.strip_chars()
        
        sub_stat_expr = df_work[sub_stat_col].cast(pl.String, strict=False).fill_null("").str.strip_chars() if sub_stat_col and sub_stat_col in df_work.columns else pl.Series([""] * len(df_work))
        main_stat_expr = df_work[main_stat_col].cast(pl.String, strict=False).fill_null("").str.strip_chars() if main_stat_col and main_stat_col in df_work.columns else norm_note_expr

        status_text = main_stat_expr + " " + sub_stat_expr

        is_contact_expr = (
            status_text.str.contains(r"توصل|تتوصل|تواصل|طلب|مهلة|اعفاء|معترف|قريب|مراجعة|منتظم|سداد|وعد|تسوية|متابعه|متابعة|يرد|رافض|مسجون|متوفي|خروج|كامل|جزئى|اقساط") &
            ~status_text.str.contains(r"عدم توصل|عدم تتوصل|الرقم لا يخص|لا يوجد ارقام|غير مستعمل|غير صحيح") &
            ~(main_stat_expr.str.contains(r"^(لايرد|لا يرد|مغلق)$") | sub_stat_expr.str.contains(r"^(لايرد|لا يرد|مغلق)$"))
        )
        is_no_answer_expr = (
            (main_stat_expr.str.contains(r"^(لايرد|لا يرد|مغلق)$") | sub_stat_expr.str.contains(r"^(لايرد|لا يرد|مغلق)$") | status_text.str.contains(r"لايرد|مغلق")) &
            ~is_contact_expr
        )
        is_closed_expr = is_no_answer_expr
        is_no_contact_expr = status_text.str.contains(r"عدم توصل|عدم تتوصل|غير مستعمل|لا يوجد|لايوجد|لا يخص|غير صحيح") & ~is_contact_expr

        df_out = df_work.with_columns([
            pl.when(is_covered_expr).then(pl.lit("Covered")).otherwise(pl.lit("Not Covered")).alias("Coverage Status"),
            pl.when(is_covered_expr).then(pl.lit(1)).otherwise(pl.lit(0)).alias("Coverage Value"),
            pl.when(is_covered_expr).then(pl.lit("تمت التغطية")).otherwise(pl.lit("لم تتم التغطية")).alias("حالة التغطية"),
            total_paid_expr.alias("مبلغ السداد"),
            count_paid_expr.alias("عدد عمليات السداد"),
            pl.when(is_contact_expr).then(1).otherwise(0).alias("عدد التوصل"),
            pl.when(~is_contact_expr).then(1).otherwise(0).alias("عدد عدم التوصل"),
            pl.when(is_no_answer_expr).then(1).otherwise(0).alias("عدد لا يرد"),
            pl.when(is_closed_expr).then(1).otherwise(0).alias("عدد مغلق"),
            (
                pl.when(total_paid_expr + bal_series > 0)
                .then((total_paid_expr / (total_paid_expr + bal_series)) * 100.0)
                .otherwise(0.0)
            ).alias("نسبة التحصيل %")
        ])

        # 5. حساب الـ Pivot Tables الشاملة لكل عنصر
        pivot_supervisor  = self._build_group_summary(df_out, sup_col or col_col, "المشرف", bal_col, supervisor_targets=supervisor_targets)
        pivot_collector   = self._build_group_summary(df_out, col_col, "المحصل", bal_col, usr_col=usr_col, sup_col=sup_col, supervisor_targets=supervisor_targets)
        pivot_portfolio   = self._build_group_summary(df_out, prt_col, "المحافظ", bal_col)
        pivot_main_status = self._build_group_summary(df_out, main_stat_col, "الحالة الرئيسية", bal_col) if main_stat_col else pl.DataFrame()
        pivot_sub_status  = self._build_group_summary(df_out, sub_stat_col, "الحالة الفرعية", bal_col) if sub_stat_col else pl.DataFrame()

        # 6. تحديث اختيار Best Supervisor & Best Collector (أفضل مشرف وأفضل محصل)
        best_supervisor_name = "غير محدد"
        best_supervisor_score = -1.0
        best_collector_name = "غير محدد"
        best_collector_score = -1.0

        if not pivot_supervisor.is_empty():
            sup_clean = pivot_supervisor.filter(~pl.col("المشرف").str.contains("📊"))
            if len(sup_clean) > 0:
                sup_clean = sup_clean.with_columns(
                    (pl.col("نسبة التغطية %").fill_null(0.0) * 0.4 + pl.col("نسبة التوصل %").fill_null(0.0) * 0.3 + pl.col("نسبة التحصيل %").fill_null(0.0) * 0.3).alias("score")
                ).sort("score", descending=True)
                best_supervisor_name = str(sup_clean["المشرف"][0])
                val = sup_clean["score"][0]
                best_supervisor_score = float(val) if val is not None else 0.0

        if not pivot_collector.is_empty():
            col_clean = pivot_collector.filter(~pl.col("المحصل").str.contains("📊"))
            if len(col_clean) > 0:
                col_clean = col_clean.with_columns(
                    (pl.col("نسبة التغطية %").fill_null(0.0) * 0.4 + pl.col("نسبة التوصل %").fill_null(0.0) * 0.3 + pl.col("نسبة التحصيل %").fill_null(0.0) * 0.3).alias("score")
                ).sort("score", descending=True)
                best_collector_name = str(col_clean["المحصل"][0])
                val = col_clean["score"][0]
                best_collector_score = float(val) if val is not None else 0.0

        # 7. الترتيب Top 10
        top10_supervisors = pivot_supervisor.filter(~pl.col("المشرف").str.contains("📊")).sort("نسبة التغطية %", descending=True).head(10) if not pivot_supervisor.is_empty() else pl.DataFrame()
        top10_collectors  = pivot_collector.filter(~pl.col("المحصل").str.contains("📊")).sort("نسبة التغطية %", descending=True).head(10) if not pivot_collector.is_empty() else pl.DataFrame()
        top10_portfolios  = pivot_portfolio.filter(~pl.col("المحافظ").str.contains("📊")).sort("متبقي سداد موثق", descending=True).head(10) if not pivot_portfolio.is_empty() else pl.DataFrame()

        # 8. حساب الـ KPIs الشاملة
        total_cust     = len(df_out)
        covered_cust   = int(df_out["Coverage Value"].sum())
        uncovered_cust = total_cust - covered_cust
        cov_rate       = round((covered_cust / total_cust * 100), 2) if total_cust > 0 else 0.0

        total_paid_val = round(float(df_out["مبلغ السداد"].sum()), 2)
        total_bal_val  = round(float(bal_series.sum()), 2)
        paid_cnt_val   = int(df_out["عدد عمليات السداد"].sum())
        avg_paid_val   = round(total_paid_val / paid_cnt_val, 2) if paid_cnt_val > 0 else 0.0
        coll_rate      = round((total_paid_val / (total_paid_val + total_bal_val) * 100), 2) if (total_paid_val + total_bal_val) > 0 else 0.0

        contact_cnt    = int(df_out["عدد التوصل"].sum())
        no_answer_cnt  = int(df_out["عدد لا يرد"].sum())
        closed_cnt     = int(df_out["عدد مغلق"].sum())

        stats = {
            "نوع التقرير": report_title,
            "الفترة الزمنية": report_period_str,
            "إجمالي العملاء": total_cust,
            "عدد العملاء المغطين": covered_cust,
            "عدد العملاء غير المغطين": uncovered_cust,
            "نسبة التغطية": f"{cov_rate}%",
            "إجمالي السداد": f"{total_paid_val:,.2f} ريال",
            "عدد عمليات السداد": paid_cnt_val,
            "إجمالي متبقي السداد الموثق": f"{total_bal_val:,.2f} ريال",
            "متوسط السداد": f"{avg_paid_val:,.2f} ريال",
            "نسبة التحصيل": f"{coll_rate}%",
            "🏆 أفضل مشرف": best_supervisor_name,
            "👑 أفضل محصل": best_collector_name,
        }

        # ── 5b. جدول ملخص الأداء البسيط (المشرف + محصليه + تغطية + مستهدف + تحصيل + مستهدف)
        perf_summary = self._build_performance_summary(
            df_out=df_out,
            sup_col=sup_col,
            col_col=col_col,
            supervisor_targets=supervisor_targets,
        )

        return {
            "report_mode": report_mode,
            "report_title": report_title,
            "report_period": report_period_str,
            "data": df_out,
            "stats": stats,
            "best_supervisor": best_supervisor_name,
            "best_collector": best_collector_name,
            "pivot_supervisor": pivot_supervisor,
            "pivot_collector": pivot_collector,
            "pivot_portfolio": pivot_portfolio,
            "pivot_main_status": pivot_main_status,
            "pivot_sub_status": pivot_sub_status,
            "top10_supervisors": top10_supervisors,
            "top10_collectors": top10_collectors,
            "top10_portfolios": top10_portfolios,
            "perf_summary": perf_summary,
        }

    def _build_group_summary(
        self,
        df: pl.DataFrame,
        group_col: Optional[str],
        label: str,
        bal_col: Optional[str],
        usr_col: Optional[str] = None,
        sup_col: Optional[str] = None,
        supervisor_targets: Optional[Dict] = None,
    ) -> pl.DataFrame:

        if not group_col or group_col not in df.columns:
            return pl.DataFrame()

        grp_cols = [group_col]
        if usr_col and usr_col in df.columns and group_col != usr_col:
            grp_cols.append(usr_col)
        if sup_col and sup_col in df.columns and group_col != sup_col:
            grp_cols.append(sup_col)

        bal_exp = _clean_float(df[bal_col]) if bal_col and bal_col in df.columns else pl.lit(0.0)

        df_work = df.with_columns([
            bal_exp.alias("_clean_bal")
        ])

        agg_df = (
            df_work
            .group_by(grp_cols)
            .agg([
                pl.len().alias("عدد العملاء"),
                pl.col("Coverage Value").sum().alias("تمت التغطية"),
                (pl.len() - pl.col("Coverage Value").sum()).alias("لم تتم التغطية"),
                pl.col("عدد التوصل").sum().alias("تم التوصل"),
                pl.col("عدد عدم التوصل").sum().alias("عدم التوصل"),
                pl.col("عدد لا يرد").sum().alias("لا يرد"),
                pl.col("عدد مغلق").sum().alias("مغلق"),
                pl.col("مبلغ السداد").sum().round(2).alias("مبلغ السداد"),
                pl.col("_clean_bal").sum().round(2).alias("متبقي سداد موثق"),
            ])
            .sort("عدد العملاء", descending=True)
        )

        agg_df = agg_df.rename({group_col: label})

        total_cust = int(agg_df["عدد العملاء"].sum())
        total_cov  = float(agg_df["تمت التغطية"].sum())
        total_cont = float(agg_df["تم التوصل"].sum())
        total_noans = float(agg_df["لا يرد"].sum())
        total_cls  = float(agg_df["مغلق"].sum())
        total_paid = float(agg_df["مبلغ السداد"].sum())
        total_bal  = float(agg_df["متبقي سداد موثق"].sum())

        total_row = {
            label: f"📊 إجمالي {label}",
            "عدد العملاء": total_cust,
            "تمت التغطية": int(total_cov),
            "لم تتم التغطية": int(agg_df["لم تتم التغطية"].sum()),
            "نسبة التغطية %": round((total_cov / total_cust * 100.0), 2) if total_cust > 0 else 0.0,
            "تم التوصل": int(total_cont),
            "عدم التوصل": int(agg_df["عدم التوصل"].sum()),
            "نسبة التوصل %": round((total_cont / total_cust * 100.0), 2) if total_cust > 0 else 0.0,
            "لا يرد": int(total_noans),
            "نسبة لايرد %": round((total_noans / total_cust * 100.0), 2) if total_cust > 0 else 0.0,
            "مغلق": int(total_cls),
            "نسبة مغلق %": round((total_cls / total_cust * 100.0), 2) if total_cust > 0 else 0.0,
            "مبلغ السداد": round(total_paid, 2),
            "متبقي سداد موثق": round(total_bal, 2),
            "نسبة التحصيل %": round((total_paid / (total_paid + total_bal) * 100.0), 2) if (total_paid + total_bal) > 0 else 0.0,
        }
        if usr_col and usr_col in grp_cols:
            total_row[usr_col] = "-"
        if sup_col and sup_col in grp_cols:
            total_row[sup_col] = "-"

        rows = agg_df.to_dicts()
        rows.append(total_row)
        return pl.DataFrame(rows, infer_schema_length=None)

    def _build_performance_summary(
        self,
        df_out: pl.DataFrame,
        sup_col: Optional[str],
        col_col: Optional[str],
        supervisor_targets: Optional[Dict] = None,
    ) -> pl.DataFrame:
        """
        ينتج جدول ملخص أداء مبسط بالكولومز التالية فقط:
          المشرف | المحصلين التابعين له | التغطية (عدد) | مستهدف التغطية | التحصيل (مبلغ) | مستهدف التحصيل | نسبة التغطية % | نسبة التحصيل %

        التغطية  → من المحفظة الأساسية مفلترة بالتاريخ المحدد (Coverage Value = 1)
        التحصيل  → مبالغ السداد من ملف السدادات مفلترة بالتاريخ المحدد (مبلغ السداد)
        المستهدفات → من supervisor_targets إن وُجدت، وإلا تُحسب نسب بدونها
        """
        if not col_col or col_col not in df_out.columns:
            return pl.DataFrame()

        # ── تجميع على مستوى المحصل
        grp_cols_col = [col_col]
        if sup_col and sup_col in df_out.columns:
            grp_cols_col.append(sup_col)

        collector_agg = (
            df_out
            .group_by(grp_cols_col)
            .agg([
                pl.col("Coverage Value").sum().alias("التغطية"),
                pl.col("مبلغ السداد").sum().round(2).alias("التحصيل"),
            ])
            .sort(sup_col if sup_col and sup_col in df_out.columns else col_col)
        )

        # ── بناء صفوف النتيجة
        rows: list[dict] = []
        supervisor_targets = supervisor_targets or {}

        # تجميع المحصلين تحت كل مشرف
        if sup_col and sup_col in collector_agg.columns:
            # نجمع على مستوى المشرف أولاً
            supervisor_groups: Dict[str, list] = {}
            for r in collector_agg.iter_rows(named=True):
                sup_name = str(r.get(sup_col) or "بدون مشرف")
                col_name = str(r.get(col_col) or "")
                supervisor_groups.setdefault(sup_name, [])
                supervisor_groups[sup_name].append({
                    "collector": col_name,
                    "coverage": float(r["التغطية"]),
                    "collection": float(r["التحصيل"]),
                })

            for sup_name, collectors_list in supervisor_groups.items():
                sup_tgt = supervisor_targets.get(sup_name, {}) if supervisor_targets else {}
                n_collectors = max(len(collectors_list), 1)

                # مستهدف المشرف الكلي (مستهدف كل محصل × عدد المحصلين)
                cov_tgt_per_col = float(sup_tgt.get("coverage_target", 0))
                col_tgt_per_col = float(sup_tgt.get("collection_target", 0))

                # ── صف إجمالي المشرف
                total_cov   = sum(c["coverage"] for c in collectors_list)
                total_col   = sum(c["collection"] for c in collectors_list)
                total_cov_tgt = cov_tgt_per_col * n_collectors
                total_col_tgt = col_tgt_per_col * n_collectors

                cov_pct = round((total_cov / total_cov_tgt * 100), 2) if total_cov_tgt > 0 else None
                col_pct = round((total_col / total_col_tgt * 100), 2) if total_col_tgt > 0 else None

                collectors_names = "، ".join(c["collector"] for c in collectors_list)

                rows.append({
                    "المشرف": sup_name,
                    "المحصلين التابعين له": collectors_names,
                    "التغطية": int(total_cov),
                    "مستهدف التغطية": int(total_cov_tgt) if total_cov_tgt > 0 else None,
                    "نسبة التغطية %": cov_pct,
                    "التحصيل": round(total_col, 2),
                    "مستهدف التحصيل": round(total_col_tgt, 2) if total_col_tgt > 0 else None,
                    "نسبة التحصيل %": col_pct,
                    "النوع": "مشرف",
                })

                # ── صف لكل محصل
                for c in collectors_list:
                    c_cov_pct = round((c["coverage"] / cov_tgt_per_col * 100), 2) if cov_tgt_per_col > 0 else None
                    c_col_pct = round((c["collection"] / col_tgt_per_col * 100), 2) if col_tgt_per_col > 0 else None
                    rows.append({
                        "المشرف": "",
                        "المحصلين التابعين له": c["collector"],
                        "التغطية": int(c["coverage"]),
                        "مستهدف التغطية": int(cov_tgt_per_col) if cov_tgt_per_col > 0 else None,
                        "نسبة التغطية %": c_cov_pct,
                        "التحصيل": round(c["collection"], 2),
                        "مستهدف التحصيل": round(col_tgt_per_col, 2) if col_tgt_per_col > 0 else None,
                        "نسبة التحصيل %": c_col_pct,
                        "النوع": "محصل",
                    })

        else:
            # لا يوجد عمود مشرف — تجميع على مستوى المحصل فقط
            for r in collector_agg.iter_rows(named=True):
                col_name = str(r.get(col_col) or "")
                cov_done = float(r["التغطية"])
                col_done = float(r["التحصيل"])
                rows.append({
                    "المشرف": "",
                    "المحصلين التابعين له": col_name,
                    "التغطية": int(cov_done),
                    "مستهدف التغطية": None,
                    "نسبة التغطية %": None,
                    "التحصيل": round(col_done, 2),
                    "مستهدف التحصيل": None,
                    "نسبة التحصيل %": None,
                    "النوع": "محصل",
                })

        if not rows:
            return pl.DataFrame()

        # ── صف الإجمالي الكلي
        grand_cov = sum(r["التغطية"] for r in rows if r.get("النوع") == "مشرف")
        grand_col = sum(r["التحصيل"] for r in rows if r.get("النوع") == "مشرف")
        grand_cov_tgt = sum((r.get("مستهدف التغطية") or 0) for r in rows if r.get("النوع") == "مشرف")
        grand_col_tgt = sum((r.get("مستهدف التحصيل") or 0) for r in rows if r.get("النوع") == "مشرف")

        rows.append({
            "المشرف": "📊 الإجمالي الكلي",
            "المحصلين التابعين له": "",
            "التغطية": grand_cov,
            "مستهدف التغطية": int(grand_cov_tgt) if grand_cov_tgt else None,
            "نسبة التغطية %": round((grand_cov / grand_cov_tgt * 100), 2) if grand_cov_tgt > 0 else None,
            "التحصيل": round(grand_col, 2),
            "مستهدف التحصيل": round(grand_col_tgt, 2) if grand_col_tgt > 0 else None,
            "نسبة التحصيل %": round((grand_col / grand_col_tgt * 100), 2) if grand_col_tgt > 0 else None,
            "النوع": "إجمالي",
        })

        return pl.DataFrame(rows, infer_schema_length=None)
