from fastmcp import FastMCP
import mysql.connector
import os


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DB_HOST = os.getenv("DB_HOST") 
DB_PORT = int(os.getenv("DB_PORT", "26238"))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD") 
DB_NAME = os.getenv("DB_NAME", "defaultdb")


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db():
    """Create and return a MySQL database connection."""

    if not DB_HOST:
        raise RuntimeError("DB_HOST environment variable is not set.")

    if not DB_USER:
        raise RuntimeError("DB_USER environment variable is not set.")

    if not DB_PASSWORD:
        raise RuntimeError("DB_PASSWORD environment variable is not set.")

    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        ssl_disabled=False,
        connection_timeout=15
    )


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():
    """Create required database tables."""

    db = get_db()
    cursor = db.cursor()

    try:

        # ----------------------------------------------------
        # EXPENSES
        # ----------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INT AUTO_INCREMENT PRIMARY KEY,
                date DATE NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                category VARCHAR(100) NOT NULL,
                sub_category VARCHAR(100) DEFAULT '',
                note TEXT DEFAULT NULL
            )
        """)

        # ----------------------------------------------------
        # INCOME
        # ----------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS income (
                id INT AUTO_INCREMENT PRIMARY KEY,
                date DATE NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                source VARCHAR(100) NOT NULL,
                note TEXT DEFAULT NULL
            )
        """)

        # ----------------------------------------------------
        # BUDGETS
        # ----------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                category VARCHAR(100) NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                month VARCHAR(7) NOT NULL,
                UNIQUE(category, month)
            )
        """)

        # ----------------------------------------------------
        # RECURRING EXPENSES
        # ----------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recurring_expenses (
                id INT AUTO_INCREMENT PRIMARY KEY,
                description VARCHAR(255) NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                category VARCHAR(100) NOT NULL,
                sub_category VARCHAR(100) DEFAULT '',
                frequency VARCHAR(50) NOT NULL,
                next_date DATE NOT NULL,
                note TEXT DEFAULT NULL
            )
        """)

        db.commit()

    finally:
        cursor.close()
        db.close()


# ============================================================
# MCP SERVER
# ============================================================

mcp = FastMCP(
    name="Expense Tracker"
)


# ============================================================
# EXPENSE TOOLS
# ============================================================

@mcp.tool
def add_expenses(
    date,
    amount,
    category,
    sub_category="",
    note=""
):
    """Add a new expense to the database."""

    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute("""
            INSERT INTO expenses
            (date, amount, category, sub_category, note)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            date,
            amount,
            category,
            sub_category,
            note
        ))

        db.commit()

        return {
            "status": "OK",
            "message": "Expense added successfully",
            "id": cursor.lastrowid
        }

    finally:
        cursor.close()
        db.close()


@mcp.tool
def list_expenses(
    start_date,
    end_date
):
    """List all expenses between two dates."""

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                id,
                date,
                amount,
                category,
                sub_category,
                note
            FROM expenses
            WHERE date BETWEEN %s AND %s
            ORDER BY date ASC, id ASC
        """, (
            start_date,
            end_date
        ))

        return cursor.fetchall()

    finally:
        cursor.close()
        db.close()


@mcp.tool
def summarize(
    start_date,
    end_date,
    category=None
):
    """Summarize expenses by category."""

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        query = """
            SELECT
                category,
                SUM(amount) AS total_amount
            FROM expenses
            WHERE date BETWEEN %s AND %s
        """

        params = [
            start_date,
            end_date
        ]

        if category:
            query += " AND category = %s"
            params.append(category)

        query += """
            GROUP BY category
            ORDER BY total_amount DESC
        """

        cursor.execute(query, params)

        return cursor.fetchall()

    finally:
        cursor.close()
        db.close()


@mcp.tool
def edit_expenses(
    id,
    date=None,
    amount=None,
    category=None,
    sub_category=None,
    note=None
):
    """Edit an existing expense by ID."""

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                date,
                amount,
                category,
                sub_category,
                note
            FROM expenses
            WHERE id = %s
        """, (id,))

        current = cursor.fetchone()

        if current is None:
            return {
                "status": "ERROR",
                "message": "Expense not found"
            }

        date = (
            date
            if date is not None
            else current["date"]
        )

        amount = (
            amount
            if amount is not None
            else current["amount"]
        )

        category = (
            category
            if category is not None
            else current["category"]
        )

        sub_category = (
            sub_category
            if sub_category is not None
            else current["sub_category"]
        )

        note = (
            note
            if note is not None
            else current["note"]
        )

        cursor.execute("""
            UPDATE expenses
            SET
                date = %s,
                amount = %s,
                category = %s,
                sub_category = %s,
                note = %s
            WHERE id = %s
        """, (
            date,
            amount,
            category,
            sub_category,
            note,
            id
        ))

        db.commit()

        return {
            "status": "OK",
            "message": "Expense updated successfully",
            "id": id
        }

    finally:
        cursor.close()
        db.close()


@mcp.tool
def delete_expenses(id):
    """Delete an expense by ID."""

    db = get_db()
    cursor = db.cursor()

    try:

        cursor.execute("""
            DELETE FROM expenses
            WHERE id = %s
        """, (id,))

        deleted = cursor.rowcount

        db.commit()

        if deleted == 0:
            return {
                "status": "ERROR",
                "message": "Expense not found"
            }

        return {
            "status": "OK",
            "message": "Expense deleted successfully",
            "id": id
        }

    finally:
        cursor.close()
        db.close()


@mcp.tool
def search_expenses(keyword):
    """Search expenses by category, sub-category or note."""

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        search = f"%{keyword}%"

        cursor.execute("""
            SELECT
                id,
                date,
                amount,
                category,
                sub_category,
                note
            FROM expenses
            WHERE category LIKE %s
               OR sub_category LIKE %s
               OR note LIKE %s
            ORDER BY date DESC
        """, (
            search,
            search,
            search
        ))

        return cursor.fetchall()

    finally:
        cursor.close()
        db.close()


@mcp.tool
def filter_expenses(
    start_date,
    end_date,
    category=None,
    min_amount=None,
    max_amount=None
):
    """Filter expenses by date, category and amount."""

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        query = """
            SELECT
                id,
                date,
                amount,
                category,
                sub_category,
                note
            FROM expenses
            WHERE date BETWEEN %s AND %s
        """

        params = [
            start_date,
            end_date
        ]

        if category:
            query += " AND category = %s"
            params.append(category)

        if min_amount is not None:
            query += " AND amount >= %s"
            params.append(min_amount)

        if max_amount is not None:
            query += " AND amount <= %s"
            params.append(max_amount)

        query += " ORDER BY date DESC"

        cursor.execute(query, params)

        return cursor.fetchall()

    finally:
        cursor.close()
        db.close()


@mcp.tool
def get_largest_expenses(
    start_date,
    end_date,
    limit=5
):
    """Get largest expenses in a date range."""

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        limit = int(limit)

        if limit < 1:
            limit = 5

        if limit > 100:
            limit = 100

        cursor.execute("""
            SELECT
                id,
                date,
                amount,
                category,
                sub_category,
                note
            FROM expenses
            WHERE date BETWEEN %s AND %s
            ORDER BY amount DESC
            LIMIT %s
        """, (
            start_date,
            end_date,
            limit
        ))

        return cursor.fetchall()

    finally:
        cursor.close()
        db.close()


# ============================================================
# INCOME TOOLS
# ============================================================

@mcp.tool
def add_income(
    date,
    amount,
    source,
    note=""
):
    """Add income or credit."""

    db = get_db()
    cursor = db.cursor()

    try:

        cursor.execute("""
            INSERT INTO income
            (date, amount, source, note)
            VALUES (%s, %s, %s, %s)
        """, (
            date,
            amount,
            source,
            note
        ))

        db.commit()

        return {
            "status": "OK",
            "message": "Income added successfully",
            "id": cursor.lastrowid
        }

    finally:
        cursor.close()
        db.close()


@mcp.tool
def list_income(
    start_date,
    end_date
):
    """List income between two dates."""

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                id,
                date,
                amount,
                source,
                note
            FROM income
            WHERE date BETWEEN %s AND %s
            ORDER BY date ASC
        """, (
            start_date,
            end_date
        ))

        return cursor.fetchall()

    finally:
        cursor.close()
        db.close()


@mcp.tool
def edit_income(
    id,
    date=None,
    amount=None,
    source=None,
    note=None
):
    """Edit an income record by ID."""

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                date,
                amount,
                source,
                note
            FROM income
            WHERE id = %s
        """, (id,))

        current = cursor.fetchone()

        if current is None:
            return {
                "status": "ERROR",
                "message": "Income not found"
            }

        date = (
            date
            if date is not None
            else current["date"]
        )

        amount = (
            amount
            if amount is not None
            else current["amount"]
        )

        source = (
            source
            if source is not None
            else current["source"]
        )

        note = (
            note
            if note is not None
            else current["note"]
        )

        cursor.execute("""
            UPDATE income
            SET
                date = %s,
                amount = %s,
                source = %s,
                note = %s
            WHERE id = %s
        """, (
            date,
            amount,
            source,
            note,
            id
        ))

        db.commit()

        return {
            "status": "OK",
            "message": "Income updated successfully",
            "id": id
        }

    finally:
        cursor.close()
        db.close()


@mcp.tool
def delete_income(id):
    """Delete income by ID."""

    db = get_db()
    cursor = db.cursor()

    try:

        cursor.execute("""
            DELETE FROM income
            WHERE id = %s
        """, (id,))

        deleted = cursor.rowcount

        db.commit()

        if deleted == 0:
            return {
                "status": "ERROR",
                "message": "Income not found"
            }

        return {
            "status": "OK",
            "message": "Income deleted successfully",
            "id": id
        }

    finally:
        cursor.close()
        db.close()


# ============================================================
# BALANCE
# ============================================================

@mcp.tool
def get_balance(
    start_date,
    end_date
):
    """Calculate income, expenses and balance."""

    db = get_db()
    cursor = db.cursor()

    try:

        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM expenses
            WHERE date BETWEEN %s AND %s
        """, (
            start_date,
            end_date
        ))

        expenses = float(cursor.fetchone()[0])

        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM income
            WHERE date BETWEEN %s AND %s
        """, (
            start_date,
            end_date
        ))

        income = float(cursor.fetchone()[0])

        return {
            "start_date": start_date,
            "end_date": end_date,
            "total_income": income,
            "total_expenses": expenses,
            "balance": income - expenses
        }

    finally:
        cursor.close()
        db.close()


# ============================================================
# DAILY SUMMARY
# ============================================================

@mcp.tool
def daily_summary(date):
    """Get financial summary for one day."""

    db = get_db()
    cursor = db.cursor()

    try:

        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM expenses
            WHERE date = %s
        """, (date,))

        expenses = float(cursor.fetchone()[0])

        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM income
            WHERE date = %s
        """, (date,))

        income = float(cursor.fetchone()[0])

        return {
            "date": date,
            "income": income,
            "expenses": expenses,
            "balance": income - expenses
        }

    finally:
        cursor.close()
        db.close()


# ============================================================
# MONTHLY SUMMARY
# ============================================================

@mcp.tool
def monthly_summary(
    year,
    month
):
    """Get complete financial summary for a month."""

    year = int(year)
    month = int(month)

    if month < 1 or month > 12:
        return {
            "status": "ERROR",
            "message": "Month must be between 1 and 12"
        }

    start_date = f"{year:04d}-{month:02d}-01"

    if month == 12:
        end_date = f"{year + 1:04d}-01-01"
    else:
        end_date = f"{year:04d}-{month + 1:02d}-01"

    db = get_db()
    cursor = db.cursor()

    try:

        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM expenses
            WHERE date >= %s
              AND date < %s
        """, (
            start_date,
            end_date
        ))

        expenses = float(cursor.fetchone()[0])

        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM income
            WHERE date >= %s
              AND date < %s
        """, (
            start_date,
            end_date
        ))

        income = float(cursor.fetchone()[0])

        return {
            "year": year,
            "month": month,
            "total_income": income,
            "total_expenses": expenses,
            "savings": income - expenses
        }

    finally:
        cursor.close()
        db.close()


# ============================================================
# BUDGET TOOLS
# ============================================================

@mcp.tool
def set_budget(
    category,
    amount,
    month
):
    """Set or update a monthly category budget."""

    db = get_db()
    cursor = db.cursor()

    try:

        cursor.execute("""
            INSERT INTO budgets
            (category, amount, month)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                amount = VALUES(amount)
        """, (
            category,
            amount,
            month
        ))

        db.commit()

        return {
            "status": "OK",
            "message": "Budget set successfully",
            "category": category,
            "amount": float(amount),
            "month": month
        }

    finally:
        cursor.close()
        db.close()


@mcp.tool
def list_budgets(month):
    """List all budgets for a month."""

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                id,
                category,
                amount,
                month
            FROM budgets
            WHERE month = %s
            ORDER BY category ASC
        """, (month,))

        return cursor.fetchall()

    finally:
        cursor.close()
        db.close()


@mcp.tool
def delete_budget(id):
    """Delete a budget by ID."""

    db = get_db()
    cursor = db.cursor()

    try:

        cursor.execute("""
            DELETE FROM budgets
            WHERE id = %s
        """, (id,))

        deleted = cursor.rowcount

        db.commit()

        if deleted == 0:
            return {
                "status": "ERROR",
                "message": "Budget not found"
            }

        return {
            "status": "OK",
            "message": "Budget deleted successfully",
            "id": id
        }

    finally:
        cursor.close()
        db.close()


@mcp.tool
def get_budget_status(month):
    """Compare budget against actual spending."""

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                id,
                category,
                amount,
                month
            FROM budgets
            WHERE month = %s
        """, (month,))

        budgets = cursor.fetchall()

        results = []

        for budget in budgets:

            cursor.execute("""
                SELECT
                    COALESCE(SUM(amount), 0) AS spent
                FROM expenses
                WHERE category = %s
                  AND date >= %s
                  AND date < DATE_ADD(%s, INTERVAL 1 MONTH)
            """, (
                budget["category"],
                f"{month}-01",
                f"{month}-01"
            ))

            row = cursor.fetchone()

            spent = float(row["spent"])
            budget_amount = float(budget["amount"])

            remaining = budget_amount - spent

            percentage = (
                (spent / budget_amount) * 100
                if budget_amount > 0
                else 0
            )

            results.append({
                "category": budget["category"],
                "budget": budget_amount,
                "spent": spent,
                "remaining": remaining,
                "usage_percentage": round(
                    percentage,
                    2
                ),
                "status": (
                    "OVER BUDGET"
                    if spent > budget_amount
                    else "WITHIN BUDGET"
                )
            })

        return results

    finally:
        cursor.close()
        db.close()


# ============================================================
# RECURRING EXPENSES
# ============================================================

@mcp.tool
def add_recurring_expense(
    description,
    amount,
    category,
    frequency,
    next_date,
    sub_category="",
    note=""
):
    """Add a recurring expense."""

    db = get_db()
    cursor = db.cursor()

    try:

        cursor.execute("""
            INSERT INTO recurring_expenses
            (
                description,
                amount,
                category,
                sub_category,
                frequency,
                next_date,
                note
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            description,
            amount,
            category,
            sub_category,
            frequency,
            next_date,
            note
        ))

        db.commit()

        return {
            "status": "OK",
            "message": "Recurring expense added successfully",
            "id": cursor.lastrowid
        }

    finally:
        cursor.close()
        db.close()


@mcp.tool
def list_recurring_expenses():
    """List all recurring expenses."""

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                id,
                description,
                amount,
                category,
                sub_category,
                frequency,
                next_date,
                note
            FROM recurring_expenses
            ORDER BY next_date ASC
        """)

        return cursor.fetchall()

    finally:
        cursor.close()
        db.close()


@mcp.tool
def delete_recurring_expense(id):
    """Delete a recurring expense."""

    db = get_db()
    cursor = db.cursor()

    try:

        cursor.execute("""
            DELETE FROM recurring_expenses
            WHERE id = %s
        """, (id,))

        deleted = cursor.rowcount

        db.commit()

        if deleted == 0:
            return {
                "status": "ERROR",
                "message": "Recurring expense not found"
            }

        return {
            "status": "OK",
            "message": "Recurring expense deleted successfully",
            "id": id
        }

    finally:
        cursor.close()
        db.close()


# ============================================================
# FINANCIAL INSIGHTS
# ============================================================

@mcp.tool
def financial_insights(
    start_date,
    end_date
):
    """Analyze spending patterns and financial statistics."""

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        # ----------------------------------------------------
        # TOTAL EXPENSES
        # ----------------------------------------------------

        cursor.execute("""
            SELECT
                COALESCE(SUM(amount), 0) AS total
            FROM expenses
            WHERE date BETWEEN %s AND %s
        """, (
            start_date,
            end_date
        ))

        total_expenses = float(
            cursor.fetchone()["total"]
        )

        # ----------------------------------------------------
        # TOTAL INCOME
        # ----------------------------------------------------

        cursor.execute("""
            SELECT
                COALESCE(SUM(amount), 0) AS total
            FROM income
            WHERE date BETWEEN %s AND %s
        """, (
            start_date,
            end_date
        ))

        total_income = float(
            cursor.fetchone()["total"]
        )

        # ----------------------------------------------------
        # CATEGORY BREAKDOWN
        # ----------------------------------------------------

        cursor.execute("""
            SELECT
                category,
                SUM(amount) AS amount
            FROM expenses
            WHERE date BETWEEN %s AND %s
            GROUP BY category
            ORDER BY amount DESC
        """, (
            start_date,
            end_date
        ))

        category_data = cursor.fetchall()

        top_category = None

        if category_data:
            top_category = {
                "category": category_data[0]["category"],
                "amount": float(
                    category_data[0]["amount"]
                )
            }

        savings = total_income - total_expenses

        savings_percentage = (
            (savings / total_income) * 100
            if total_income > 0
            else 0
        )

        return {
            "period": {
                "start_date": start_date,
                "end_date": end_date
            },
            "total_income": total_income,
            "total_expenses": total_expenses,
            "savings": savings,
            "savings_percentage": round(
                savings_percentage,
                2
            ),
            "top_spending_category": top_category,
            "category_breakdown": [
                {
                    "category": item["category"],
                    "amount": float(item["amount"])
                }
                for item in category_data
            ]
        }

    finally:
        cursor.close()
        db.close()


# ============================================================
# MCP RESOURCE
# ============================================================

@mcp.resource(
    "expense://categories",
    mime_type="application/json"
)
def categories():
    """Return available expense categories."""

    categories_path = os.path.join(
        os.path.dirname(__file__),
        "categories.json"
    )

    with open(
        categories_path,
        "r",
        encoding="utf-8"
    ) as file:
        return file.read()


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":

    # Database initialization happens ONLY when
    # the server is actually started.
    #
    # FastMCP Cloud build/inspect will import this file,
    # but it will NOT execute init_db().

    init_db()

    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=8000
    )
