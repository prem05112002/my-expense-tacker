
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_, update, delete
from typing import List
from .. import models, schemas

async def preview_rule_changes(db: AsyncSession, pattern: str, match_type: str):
    query = select(models.Transaction)
    if match_type == "CONTAINS":
        query = query.where(models.Transaction.merchant_name.ilike(f"%{pattern}%"))
    elif match_type == "EXACT":
        query = query.where(models.Transaction.merchant_name == pattern)
    query = query.order_by(desc(models.Transaction.txn_date))
    result = await db.execute(query)
    return result.scalars().all()

async def create_rule(db: AsyncSession, rule_data: schemas.RuleCreate):
    rule_dict = rule_data.model_dump(exclude={"excluded_ids"})
    new_rule = models.TransactionRule(**rule_dict)
    db.add(new_rule)
    await db.commit()
    await db.refresh(new_rule)
    await apply_rule_historical(db, new_rule, rule_data.excluded_ids)
    stmt = select(models.Category).where(models.Category.id == new_rule.category_id)
    result = await db.execute(stmt)
    category = result.scalar_one_or_none()
    return {
        **new_rule.__dict__, 
        "category_name": category.name if category else "Uncategorized",
        "category_color": category.color if category else "#cbd5e1"
    }

async def apply_rule_historical(db: AsyncSession, rule: models.TransactionRule, excluded_ids: List[int] = []):
    if rule.match_type == "CONTAINS":
        filter_condition = models.Transaction.merchant_name.ilike(f"%{rule.pattern}%")
    elif rule.match_type == "EXACT":
        filter_condition = (models.Transaction.merchant_name == rule.pattern)
    else:
        return
    stmt = (
        update(models.Transaction)
        .where(filter_condition)
        .values(merchant_name=rule.new_merchant_name, category_id=rule.category_id)
    )
    if excluded_ids:
        stmt = stmt.where(models.Transaction.id.not_in(excluded_ids))
    stmt = stmt.execution_options(synchronize_session=False) 
    await db.execute(stmt)
    await db.commit()

async def get_all_rules(db: AsyncSession):
    stmt = (
        select(models.TransactionRule.id, models.TransactionRule.pattern, models.TransactionRule.new_merchant_name, models.TransactionRule.match_type, models.TransactionRule.category_id, models.Category.name.label("category_name"), models.Category.color.label("category_color"))
        .join(models.Category, models.TransactionRule.category_id == models.Category.id)
    )
    result = await db.execute(stmt)
    return result.mappings().all()

async def apply_rules_to_single_transaction(db: AsyncSession, txn: models.Transaction):
    rules_stmt = select(models.TransactionRule)
    rules_res = await db.execute(rules_stmt)
    rules = rules_res.scalars().all()
    for rule in rules:
        is_match = False
        if rule.match_type == "CONTAINS" and rule.pattern.lower() in txn.merchant_name.lower():
            is_match = True
        elif rule.match_type == "EXACT" and rule.pattern.lower() == txn.merchant_name.lower():
            is_match = True
        if is_match:
            print(f"✨ Auto-Rule Applied: {txn.merchant_name} -> {rule.new_merchant_name}")
            txn.merchant_name = rule.new_merchant_name
            txn.category_id = rule.category_id
            break 

async def get_or_create_settings(db: AsyncSession):
    stmt = select(models.UserSettings).limit(1)
    result = await db.execute(stmt)
    settings = result.scalar_one_or_none()
    if not settings:
        settings = models.UserSettings(salary_day=1, budget_type="PERCENTAGE", budget_value=40.0)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings

async def update_settings(db: AsyncSession, data: schemas.UserSettingsUpdate):
    settings = await get_or_create_settings(db)
    settings.salary_day = data.salary_day
    settings.budget_type = data.budget_type
    settings.budget_value = data.budget_value
    if data.ignored_categories is not None: settings.ignored_categories = ",".join(data.ignored_categories)
    else: settings.ignored_categories = ""
    if data.income_categories is not None: settings.income_categories = ",".join(data.income_categories)
    else: settings.income_categories = ""
    settings.view_cycle_offset = data.view_cycle_offset
    await db.commit()
    await db.refresh(settings)
    return settings