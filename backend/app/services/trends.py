from datetime import date, timedelta
from typing import Any, Dict, List, Tuple
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from .. import models
from ..schemas import trends as trend_schemas
from .rules import get_or_create_settings


async def _fetch_all_transactions(
    db: AsyncSession,
    months_back: int = 12
) -> List[Any]:
    """Fetch transactions for the analysis period."""
    cutoff_date = date.today() - timedelta(days=months_back * 30)
    stmt = (
        select(
            models.Transaction.id,
            models.Transaction.amount,
            models.Transaction.txn_date,
            models.Transaction.payment_type,
            models.Transaction.merchant_name,
            models.Category.name.label("category_name"),
            models.Category.color.label("category_color")
        )
        .join(models.Category, models.Transaction.category_id == models.Category.id)
        .where(models.Transaction.txn_date >= cutoff_date)
        .order_by(models.Transaction.txn_date.asc())
    )
    result = await db.execute(stmt)
    return result.mappings().all()


def _get_month_key(d: date) -> str:
    """Return YYYY-MM format."""
    return f"{d.year}-{d.month:02d}"


def _calculate_monthly_spending(
    transactions: List[Any],
    ignored_cats: List[str],
    income_cats: List[str]
) -> List[trend_schemas.MonthlySpend]:
    """Aggregate spending by month."""
    monthly_data: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"total": 0.0, "count": 0}
    )

    for txn in transactions:
        if txn.category_name in ignored_cats or txn.category_name in income_cats:
            continue
        p_type = (txn.payment_type or "").upper()
        if p_type != "DEBIT":
            continue

        month_key = _get_month_key(txn.txn_date)
        monthly_data[month_key]["total"] += float(txn.amount)
        monthly_data[month_key]["count"] += 1

    result = [
        trend_schemas.MonthlySpend(
            month=k,
            total=round(v["total"], 2),
            transaction_count=v["count"]
        )
        for k, v in sorted(monthly_data.items())
    ]
    return result


def _calculate_category_trends(
    transactions: List[Any],
    ignored_cats: List[str],
    income_cats: List[str]
) -> List[trend_schemas.CategoryTrend]:
    """Calculate trend direction for each category.

    Compares the most recent complete month with the previous complete month
    to avoid skewed comparisons with incomplete current month data.
    """
    today = date.today()
    # Use the two most recent COMPLETE months for fair comparison
    # prev_month = the month before current (most recent complete)
    # prev_prev_month = the month before that
    prev_month_date = today.replace(day=1) - timedelta(days=1)
    prev_month = _get_month_key(prev_month_date)
    prev_prev_month_date = prev_month_date.replace(day=1) - timedelta(days=1)
    prev_prev_month = _get_month_key(prev_prev_month_date)

    category_monthly: Dict[str, Dict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    category_colors: Dict[str, str] = {}

    for txn in transactions:
        if txn.category_name in ignored_cats or txn.category_name in income_cats:
            continue
        p_type = (txn.payment_type or "").upper()
        if p_type != "DEBIT":
            continue

        month_key = _get_month_key(txn.txn_date)
        category_monthly[txn.category_name][month_key] += float(txn.amount)
        category_colors[txn.category_name] = txn.category_color or "#cbd5e1"

    result = []
    for cat_name, monthly in category_monthly.items():
        # Compare the two most recent complete months
        curr = monthly.get(prev_month, 0.0)  # Most recent complete month
        prev = monthly.get(prev_prev_month, 0.0)  # Month before that

        if prev > 0:
            change_pct = ((curr - prev) / prev) * 100
        else:
            change_pct = 100.0 if curr > 0 else 0.0

        if change_pct > 10:
            trend = "increasing"
        elif change_pct < -10:
            trend = "decreasing"
        else:
            trend = "stable"

        result.append(trend_schemas.CategoryTrend(
            category=cat_name,
            color=category_colors.get(cat_name, "#cbd5e1"),
            current_month=round(curr, 2),
            previous_month=round(prev, 2),
            trend=trend,
            change_percent=round(change_pct, 1)
        ))

    result.sort(key=lambda x: x.current_month, reverse=True)
    return result


def _calculate_seasonal_patterns(
    transactions: List[Any],
    ignored_cats: List[str],
    income_cats: List[str]
) -> List[trend_schemas.SeasonalPattern]:
    """Identify high-spend months across the year."""
    monthly_totals: Dict[int, List[float]] = defaultdict(list)
    month_names = [
        "", "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]

    # Group by month number across years
    year_month_data: Dict[Tuple[int, int], float] = defaultdict(float)

    for txn in transactions:
        if txn.category_name in ignored_cats or txn.category_name in income_cats:
            continue
        p_type = (txn.payment_type or "").upper()
        if p_type != "DEBIT":
            continue

        key = (txn.txn_date.year, txn.txn_date.month)
        year_month_data[key] += float(txn.amount)

    for (year, month), total in year_month_data.items():
        monthly_totals[month].append(total)

    # Calculate averages
    result = []
    averages = []
    for month in range(1, 13):
        values = monthly_totals.get(month, [])
        avg = sum(values) / len(values) if values else 0.0
        averages.append(avg)
        result.append({
            "month": month,
            "month_name": month_names[month],
            "average_spend": round(avg, 2)
        })

    # Determine high-spend threshold (> 1.2x overall average)
    overall_avg = sum(averages) / len(averages) if averages else 0
    threshold = overall_avg * 1.2

    return [
        trend_schemas.SeasonalPattern(
            month=r["month"],
            month_name=r["month_name"],
            average_spend=r["average_spend"],
            is_high_spend=r["average_spend"] > threshold
        )
        for r in result
    ]


def _calculate_day_of_week_analysis(
    transactions: List[Any],
    ignored_cats: List[str],
    income_cats: List[str]
) -> List[trend_schemas.DayOfWeekSpend]:
    """Average spending by day of week."""
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_totals: Dict[int, List[float]] = defaultdict(list)
    day_counts: Dict[int, int] = defaultdict(int)

    for txn in transactions:
        if txn.category_name in ignored_cats or txn.category_name in income_cats:
            continue
        p_type = (txn.payment_type or "").upper()
        if p_type != "DEBIT":
            continue

        weekday = txn.txn_date.weekday()
        day_totals[weekday].append(float(txn.amount))
        day_counts[weekday] += 1

    return [
        trend_schemas.DayOfWeekSpend(
            day=d,
            day_name=day_names[d],
            average_spend=round(
                sum(day_totals.get(d, [])) / len(day_totals[d]) if day_totals.get(d) else 0, 2
            ),
            transaction_count=day_counts.get(d, 0)
        )
        for d in range(7)
    ]


def _detect_recurring_patterns(
    transactions: List[Any],
    ignored_cats: List[str],
    income_cats: List[str]
) -> List[trend_schemas.RecurringPattern]:
    """Identify merchants with regular transactions."""
    merchant_data: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for txn in transactions:
        if txn.category_name in ignored_cats or txn.category_name in income_cats:
            continue
        p_type = (txn.payment_type or "").upper()
        if p_type != "DEBIT":
            continue

        merchant = (txn.merchant_name or "Unknown").strip()
        if len(merchant) < 3:
            continue

        merchant_data[merchant].append({
            "date": txn.txn_date,
            "amount": float(txn.amount)
        })

    result = []
    for merchant, txns in merchant_data.items():
        if len(txns) < 3:
            continue

        txns.sort(key=lambda x: x["date"])
        dates = [t["date"] for t in txns]
        amounts = [t["amount"] for t in txns]

        # Calculate average gap between transactions
        gaps = [(dates[i+1] - dates[i]).days for i in range(len(dates) - 1)]
        avg_gap = sum(gaps) / len(gaps) if gaps else 0

        # Determine frequency
        if 5 <= avg_gap <= 9:
            frequency = "weekly"
        elif 12 <= avg_gap <= 18:
            frequency = "bi-weekly"
        elif 25 <= avg_gap <= 35:
            frequency = "monthly"
        else:
            continue  # Not a clear recurring pattern

        result.append(trend_schemas.RecurringPattern(
            merchant_name=merchant,
            frequency=frequency,
            average_amount=round(sum(amounts) / len(amounts), 2),
            occurrence_count=len(txns),
            last_occurrence=dates[-1]
        ))

    result.sort(key=lambda x: x.occurrence_count, reverse=True)
    return result[:10]  # Top 10 recurring


async def get_trends_overview(db: AsyncSession) -> trend_schemas.TrendsOverview:
    """Generate comprehensive trends analysis."""
    settings = await get_or_create_settings(db)
    ignored = [x.strip() for x in settings.ignored_categories.split(',')] if settings.ignored_categories else []
    income_cats = [x.strip() for x in settings.income_categories.split(',')] if settings.income_categories else []

    transactions = await _fetch_all_transactions(db, months_back=12)

    if not transactions:
        today = date.today()
        return trend_schemas.TrendsOverview(
            monthly_spending=[],
            category_trends=[],
            seasonal_patterns=[],
            day_of_week_analysis=[],
            recurring_patterns=[],
            total_transactions_analyzed=0,
            analysis_period_start=today - timedelta(days=365),
            analysis_period_end=today
        )

    dates = [txn.txn_date for txn in transactions]

    return trend_schemas.TrendsOverview(
        monthly_spending=_calculate_monthly_spending(transactions, ignored, income_cats),
        category_trends=_calculate_category_trends(transactions, ignored, income_cats),
        seasonal_patterns=_calculate_seasonal_patterns(transactions, ignored, income_cats),
        day_of_week_analysis=_calculate_day_of_week_analysis(transactions, ignored, income_cats),
        recurring_patterns=_detect_recurring_patterns(transactions, ignored, income_cats),
        total_transactions_analyzed=len(transactions),
        analysis_period_start=min(dates),
        analysis_period_end=max(dates)
    )


async def get_category_trend_detail(
    db: AsyncSession,
    category_name: str
) -> trend_schemas.CategoryTrendDetail:
    """Get detailed trend for a specific category.

    Average and trend calculations exclude the current incomplete month.
    """
    settings = await get_or_create_settings(db)
    ignored = [x.strip() for x in settings.ignored_categories.split(',')] if settings.ignored_categories else []
    income_cats = [x.strip() for x in settings.income_categories.split(',')] if settings.income_categories else []

    transactions = await _fetch_all_transactions(db, months_back=12)

    # Filter for specific category
    cat_txns = [
        txn for txn in transactions
        if txn.category_name == category_name
        and txn.category_name not in ignored
        and txn.category_name not in income_cats
        and (txn.payment_type or "").upper() == "DEBIT"
    ]

    if not cat_txns:
        return trend_schemas.CategoryTrendDetail(
            category=category_name,
            color="#cbd5e1",
            monthly_data=[],
            average_monthly=0.0,
            total_spend=0.0,
            trend="stable",
            peak_month="N/A",
            transaction_count=0
        )

    color = cat_txns[0].category_color or "#cbd5e1"

    # Current month key for exclusion from averages
    today = date.today()
    current_month = _get_month_key(today)

    # Monthly breakdown
    monthly_data: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"total": 0.0, "count": 0}
    )

    for txn in cat_txns:
        month_key = _get_month_key(txn.txn_date)
        monthly_data[month_key]["total"] += float(txn.amount)
        monthly_data[month_key]["count"] += 1

    monthly_list = [
        trend_schemas.MonthlySpend(
            month=k,
            total=round(v["total"], 2),
            transaction_count=v["count"]
        )
        for k, v in sorted(monthly_data.items())
    ]

    # For averages and totals, exclude current incomplete month
    complete_months = [m for m in monthly_list if m.month != current_month]
    totals = [m.total for m in complete_months]
    total_spend = sum(totals)
    avg_monthly = total_spend / len(totals) if totals else 0

    peak_month = max(complete_months, key=lambda x: x.total).month if complete_months else "N/A"

    # Trend calculation: compare two most recent COMPLETE months
    if len(complete_months) >= 2:
        recent = complete_months[-1].total
        prev = complete_months[-2].total
        if prev > 0:
            change = ((recent - prev) / prev) * 100
        else:
            change = 100.0 if recent > 0 else 0.0

        if change > 10:
            trend = "increasing"
        elif change < -10:
            trend = "decreasing"
        else:
            trend = "stable"
    else:
        trend = "stable"

    return trend_schemas.CategoryTrendDetail(
        category=category_name,
        color=color,
        monthly_data=monthly_list,
        average_monthly=round(avg_monthly, 2),
        total_spend=round(total_spend, 2),
        trend=trend,
        peak_month=peak_month,
        transaction_count=len(cat_txns)
    )


async def _calculate_avg_monthly_salary(
    db: AsyncSession,
    income_cats: List[str],
    months_back: int = 12
) -> float:
    """Calculate average monthly salary from income transactions.

    Excludes current month as it may be incomplete.
    """
    today = date.today()
    # Use end of previous month to avoid incomplete current month
    end_of_prev_month = today.replace(day=1) - timedelta(days=1)
    cutoff_date = end_of_prev_month - timedelta(days=months_back * 30)

    stmt = (
        select(
            models.Transaction.amount,
            models.Transaction.txn_date
        )
        .join(models.Category, models.Transaction.category_id == models.Category.id)
        .where(
            models.Transaction.txn_date >= cutoff_date,
            models.Transaction.txn_date <= end_of_prev_month,
            func.upper(models.Transaction.payment_type) == 'CREDIT',
            models.Category.name.in_(income_cats)
        )
    )
    result = await db.execute(stmt)
    transactions = result.mappings().all()

    if not transactions:
        return 0.0

    # Group by month and calculate average
    monthly_income: Dict[str, float] = defaultdict(float)
    for txn in transactions:
        month_key = _get_month_key(txn.txn_date)
        monthly_income[month_key] += float(txn.amount)

    totals = list(monthly_income.values())
    return sum(totals) / len(totals) if totals else 0.0


async def simulate_affordability(
    db: AsyncSession,
    simulation: trend_schemas.AffordabilitySimulation
) -> trend_schemas.AffordabilityResult:
    """Simulate budget impact of a new recurring expense.

    Uses only complete months for average calculation to avoid skewed results
    from incomplete current month data.
    """
    settings = await get_or_create_settings(db)
    ignored = [x.strip() for x in settings.ignored_categories.split(',')] if settings.ignored_categories else []
    income_cats = [x.strip() for x in settings.income_categories.split(',')] if settings.income_categories else []

    transactions = await _fetch_all_transactions(db, months_back=3)

    # Exclude current month (incomplete data)
    today = date.today()
    current_month = _get_month_key(today)

    # Calculate average monthly spend from complete months only
    monthly_totals: Dict[str, float] = defaultdict(float)

    for txn in transactions:
        if txn.category_name in ignored or txn.category_name in income_cats:
            continue
        p_type = (txn.payment_type or "").upper()
        if p_type != "DEBIT":
            continue

        month_key = _get_month_key(txn.txn_date)
        # Skip current incomplete month
        if month_key == current_month:
            continue
        monthly_totals[month_key] += float(txn.amount)

    totals = list(monthly_totals.values())
    avg_spend = sum(totals) / len(totals) if totals else 0

    # Calculate budget based on budget_type
    if settings.budget_type == "PERCENTAGE":
        avg_salary = await _calculate_avg_monthly_salary(db, income_cats)
        if avg_salary > 0:
            budget = avg_salary * (settings.budget_value / 100)
        else:
            # No salary data found - cannot calculate percentage-based budget
            return trend_schemas.AffordabilityResult(
                can_afford=False,
                current_budget=0.0,
                current_avg_spend=round(avg_spend, 2),
                projected_spend_with_new=round(avg_spend + simulation.monthly_expense, 2),
                budget_remaining_after=0.0,
                impact_percent=0.0,
                recommendation="Unable to calculate budget: No income transactions found in configured income categories. Please add salary/income transactions or switch to a fixed budget."
            )
    else:
        budget = float(settings.monthly_budget or settings.budget_value)

    projected_with_new = avg_spend + simulation.monthly_expense
    remaining_after = budget - projected_with_new
    impact_pct = (simulation.monthly_expense / budget * 100) if budget > 0 else 0

    can_afford = remaining_after >= 0

    if can_afford:
        if remaining_after > budget * 0.2:
            recommendation = "You can comfortably afford this expense."
        elif remaining_after > budget * 0.1:
            recommendation = "Affordable, but consider reducing discretionary spending."
        else:
            recommendation = "Tight budget. Consider cutting other expenses first."
    else:
        recommendation = f"Not recommended. You'd exceed your budget by {abs(remaining_after):.2f}."

    return trend_schemas.AffordabilityResult(
        can_afford=can_afford,
        current_budget=round(budget, 2),
        current_avg_spend=round(avg_spend, 2),
        projected_spend_with_new=round(projected_with_new, 2),
        budget_remaining_after=round(remaining_after, 2),
        impact_percent=round(impact_pct, 1),
        recommendation=recommendation
    )
