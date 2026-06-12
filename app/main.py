from __future__ import annotations

import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import plotly.express as px
import pandas as pd
import streamlit as st

from app.policy_engine import PolicyLibrary
from app.receipt_reader import extract_text, parse_receipt
from app.reviewer import review_line_item
from app.storage import execute, rows, seed_employees, setup_database

POLICY_DIR = ROOT / "data" / "policies"
SEED_DIR = ROOT / "data" / "seed_submissions"

st.set_page_config(
    page_title="Northwind Expense Reviewer",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

[data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #f8fafc 0%, #eef2ff 45%, #fdf2f8 100%);
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f172a 0%, #1e293b 60%, #312e81 100%);
}

[data-testid="stSidebar"] * {
    color: white !important;
}

.main-title {
    font-size: 44px;
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 8px;
}

.sub-title {
    font-size: 16px;
    color: #64748b;
    margin-bottom: 30px;
}

.section-title {
    font-size: 30px;
    font-weight: 900;
    color: #111827;
    margin-top: 15px;
    margin-bottom: 8px;
}

.section-caption {
    color: #64748b;
    font-size: 15px;
    margin-bottom: 22px;
}

.glass-card {
    background: rgba(255,255,255,0.90);
    padding: 26px;
    border-radius: 24px;
    box-shadow: 0 18px 45px rgba(15,23,42,0.10);
    border: 1px solid rgba(255,255,255,0.9);
    margin-bottom: 24px;
}

.metric-card {
    background: white;
    padding: 22px;
    border-radius: 22px;
    box-shadow: 0 14px 35px rgba(15,23,42,0.10);
    border: 1px solid #e5e7eb;
    border-left: 7px solid #6366f1;
    min-height: 125px;
}

.metric-title {
    color: #64748b;
    font-size: 14px;
    font-weight: 700;
    margin-bottom: 10px;
}

.metric-value {
    color: #0f172a;
    font-size: 30px;
    font-weight: 900;
}

.review-card {
    background: white;
    padding: 26px;
    border-radius: 24px;
    box-shadow: 0 16px 40px rgba(15,23,42,0.10);
    border: 1px solid #e5e7eb;
    margin-bottom: 24px;
}

.review-file {
    font-size: 20px;
    font-weight: 800;
    color: #111827;
}

.status-compliant {
    color: #16a34a;
    font-size: 25px;
    font-weight: 900;
}

.status-flagged {
    color: #f59e0b;
    font-size: 25px;
    font-weight: 900;
}

.status-rejected {
    color: #dc2626;
    font-size: 25px;
    font-weight: 900;
}

.status-review {
    color: #2563eb;
    font-size: 25px;
    font-weight: 900;
}

.stButton > button {
    background: linear-gradient(90deg, #6366f1, #ec4899);
    color: white;
    border: none;
    border-radius: 14px;
    padding: 11px 24px;
    font-weight: 800;
    box-shadow: 0 10px 25px rgba(99,102,241,0.25);
}

.stButton > button:hover {
    color: white;
    border: none;
    transform: translateY(-1px);
}

[data-testid="stDataFrame"] {
    border-radius: 18px;
    overflow: hidden;
    box-shadow: 0 12px 30px rgba(15,23,42,0.08);
}

hr {
    margin-top: 28px;
    margin-bottom: 28px;
}
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_policy_library() -> PolicyLibrary:
    return PolicyLibrary(POLICY_DIR)


def bootstrap() -> None:
    setup_database()
    seed_employees(SEED_DIR)


def employee_options() -> dict[str, int]:
    data = rows("SELECT id, name, department, grade FROM employees ORDER BY name")
    return {
        f"{r['name']} · Grade {r['grade']} · {r['department']}": r["id"]
        for r in data
    }


def row_to_dict(row) -> dict:
    return {key: row[key] for key in row.keys()}


def app_header() -> None:
    st.markdown("""
    <div class="main-title">🚚 Northwind Logistics AI Expense Reviewer</div>
    <div class="sub-title">
        AI-powered receipt compliance, policy citation, reviewer override, and audit-ready expense intelligence.
    </div>
    """, unsafe_allow_html=True)


def create_employee_form() -> int | None:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)

    with st.form("new_employee"):
        st.markdown('<div class="section-title">Create New Employee</div>', unsafe_allow_html=True)

        c1, c2 = st.columns(2)

        with c1:
            name = st.text_input("Employee name")
            employee_code = st.text_input("Employee ID")
            grade = st.number_input("Grade", min_value=1, max_value=10, value=3)

        with c2:
            department = st.text_input("Department")
            manager = st.text_input("Manager")

        purpose = st.text_area("Trip purpose")

        c3, c4 = st.columns(2)

        with c3:
            start = st.date_input("Trip start")

        with c4:
            end = st.date_input("Trip end")

        submitted = st.form_submit_button("Save employee")

    st.markdown("</div>", unsafe_allow_html=True)

    if submitted and name and employee_code:
        raw = {
            "name": name,
            "employee_id": employee_code,
            "grade": grade,
            "department": department,
            "manager": manager,
            "trip_purpose": purpose,
            "trip_start": str(start),
            "trip_end": str(end),
        }

        return execute(
            """
            INSERT INTO employees
            (employee_id, name, grade, department, manager, trip_purpose, trip_start, trip_end, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                employee_code,
                name,
                grade,
                department,
                manager,
                purpose,
                str(start),
                str(end),
                json.dumps(raw),
            ),
        )

    return None


def verdict_class(verdict: str) -> str:
    if verdict == "Compliant":
        return "status-compliant"
    if verdict == "Flagged":
        return "status-flagged"
    if verdict == "Rejected":
        return "status-rejected"
    return "status-review"


def verdict_icon(verdict: str) -> str:
    return {
        "Compliant": "✅",
        "Flagged": "⚠️",
        "Rejected": "⛔",
        "Needs Human Review": "👀",
    }.get(verdict, "📌")


def metric_card(title: str, value: str, color: str = "#6366f1") -> None:
    st.markdown(f"""
    <div class="metric-card" style="border-left-color:{color};">
        <div class="metric-title">{title}</div>
        <div class="metric-value">{value}</div>
    </div>
    """, unsafe_allow_html=True)


def submission_builder(policies: PolicyLibrary) -> None:
    st.markdown('<div class="section-title">Start Expense Review</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-caption">Create a new submission, upload receipts, and generate AI policy review.</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="glass-card">', unsafe_allow_html=True)

    mode = st.radio("Employee", ["Pick existing", "Create new"], horizontal=True)
    employee_id = None

    if mode == "Pick existing":
        options = employee_options()
        selected = st.selectbox("Select employee", list(options.keys()))
        employee_id = options.get(selected)
    else:
        employee_id = create_employee_form()
        if employee_id:
            st.success("Employee saved. You can now upload receipts below.")

    title = st.text_input("Submission title", value="Business trip receipt review")

    uploaded_files = st.file_uploader(
        "Upload receipts",
        type=["pdf", "png", "jpg", "jpeg", "webp", "txt", "csv"],
        accept_multiple_files=True,
    )

    review_clicked = st.button(
        "Review Receipts",
        type="primary",
        disabled=not employee_id or not uploaded_files,
    )

    st.markdown("</div>", unsafe_allow_html=True)

    if review_clicked:
        employee = row_to_dict(rows("SELECT * FROM employees WHERE id = ?", (employee_id,))[0])

        submission_id = execute(
            "INSERT INTO submissions (employee_id, title, status) VALUES (?, ?, ?)",
            (employee_id, title or "Expense Review", "reviewed"),
        )

        progress = st.progress(0)
        total_files = len(uploaded_files)

        for index, file in enumerate(uploaded_files, start=1):
            text = extract_text(file, file.name)
            receipt = parse_receipt(text, file.name)
            review = review_line_item(receipt, employee, policies)

            execute(
                """
                INSERT INTO line_items
                (submission_id, filename, vendor, category, amount, verdict, confidence, reasoning, policy_quotes, extracted_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    submission_id,
                    file.name,
                    receipt["vendor"],
                    receipt["category"],
                    receipt["amount"],
                    review["verdict"],
                    review["confidence"],
                    review["reasoning"],
                    json.dumps(review["policy_quotes"]),
                    receipt["text"],
                ),
            )

            progress.progress(index / total_files)

        st.success("Review completed and saved.")
        st.session_state["last_submission"] = submission_id

        st.markdown("## 📋 Review Results")

        latest_items = rows(
            "SELECT * FROM line_items WHERE submission_id = ? ORDER BY id",
            (submission_id,),
        )

        for item in latest_items:
            show_line_item(item)


def show_line_item(item) -> None:
    verdict = item["verdict"]
    css_class = verdict_class(verdict)
    icon = verdict_icon(verdict)
    confidence = (item["confidence"] or 0) * 100
    amount = item["amount"] or 0

    st.markdown(f"""
    <div class="review-card">
        <div class="review-file">🧾 {item['filename']}</div>
        <br>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:18px;">
            <div>
                <div style="color:#64748b;font-weight:700;">Vendor</div>
                <div style="font-size:19px;font-weight:800;">{item['vendor'] or 'Unknown'}</div>
            </div>
            <div>
                <div style="color:#64748b;font-weight:700;">Category</div>
                <div style="font-size:19px;font-weight:800;">{item['category'] or 'Unknown'}</div>
            </div>
            <div>
                <div style="color:#64748b;font-weight:700;">Amount</div>
                <div style="font-size:19px;font-weight:800;">${amount:,.2f}</div>
            </div>
            <div>
                <div style="color:#64748b;font-weight:700;">Confidence</div>
                <div style="font-size:19px;font-weight:800;">{confidence:.0f}%</div>
            </div>
        </div>
        <br>
        <div class="{css_class}">{icon} {verdict}</div>
        <p style="color:#334155;font-size:15px;margin-top:10px;">{item['reasoning']}</p>
    </div>
    """, unsafe_allow_html=True)

    quotes = json.loads(item["policy_quotes"] or "[]")

    with st.expander("📚 Policy evidence"):
        if quotes:
            for quote in quotes:
                st.markdown(f"**{quote['document']}** · Score `{quote['score']}`")
                st.info(quote["quote"])
        else:
            st.warning("No policy quote found.")

    existing = rows(
        "SELECT * FROM overrides WHERE line_item_id = ? ORDER BY created_at DESC",
        (item["id"],),
    )

    if existing:
        st.warning(
            f"Latest override: **{existing[0]['new_verdict']}** — {existing[0]['comment']}"
        )

    with st.form(f"override_{item['id']}"):
        st.markdown("#### Manager Override")
        new_verdict = st.selectbox(
            "Override verdict",
            ["Compliant", "Flagged", "Rejected", "Needs Human Review"],
        )
        comment = st.text_area("Reviewer comment")

        if st.form_submit_button("Save override") and comment.strip():
            execute(
                "INSERT INTO overrides (line_item_id, new_verdict, comment) VALUES (?, ?, ?)",
                (item["id"], new_verdict, comment.strip()),
            )
            st.success("Override saved with audit trail.")
            st.rerun()


def history_view() -> None:
    st.markdown('<div class="section-title">Submission History</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-caption">Search and filter past expense reviews by employee, status, date, department, and vendor.</div>',
        unsafe_allow_html=True,
    )

    employees = rows("SELECT id, name FROM employees ORDER BY name")
    employee_map = {"All Employees": None}
    employee_map.update({r["name"]: r["id"] for r in employees})

    with st.container():
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            selected_employee = st.selectbox("Employee", list(employee_map.keys()))

        with c2:
            selected_status = st.selectbox(
                "Status",
                ["All Statuses", "reviewed", "draft", "submitted", "closed"],
            )

        with c3:
            start_date = st.date_input("From Date", value=None)

        with c4:
            end_date = st.date_input("To Date", value=None)

        search_text = st.text_input("Search title, employee, department, vendor, or category")

    query = """
        SELECT DISTINCT
            s.id,
            s.title,
            s.status,
            s.created_at,
            e.name,
            e.department
        FROM submissions s
        JOIN employees e ON e.id = s.employee_id
        LEFT JOIN line_items l ON l.submission_id = s.id
        WHERE 1 = 1
    """

    params = []

    if employee_map[selected_employee]:
        query += " AND e.id = ?"
        params.append(employee_map[selected_employee])

    if selected_status != "All Statuses":
        query += " AND s.status = ?"
        params.append(selected_status)

    if start_date:
        query += " AND DATE(s.created_at) >= DATE(?)"
        params.append(str(start_date))

    if end_date:
        query += " AND DATE(s.created_at) <= DATE(?)"
        params.append(str(end_date))

    if search_text.strip():
        query += """
            AND (
                LOWER(s.title) LIKE ?
                OR LOWER(e.name) LIKE ?
                OR LOWER(e.department) LIKE ?
                OR LOWER(l.vendor) LIKE ?
                OR LOWER(l.category) LIKE ?
            )
        """
        pattern = f"%{search_text.lower().strip()}%"
        params.extend([pattern, pattern, pattern, pattern, pattern])

    query += " ORDER BY s.created_at DESC"

    data = rows(query, tuple(params))

    if not data:
        st.info("No submissions found for the selected filters.")
        return

    frame = pd.DataFrame([dict(r) for r in data])
    st.dataframe(frame, use_container_width=True, hide_index=True)

    selected = st.selectbox(
        "Open submission",
        [f"#{r['id']} · {r['name']} · {r['created_at']}" for r in data],
    )

    submission_id = int(selected.split("·")[0].replace("#", "").strip())

    items = rows(
        "SELECT * FROM line_items WHERE submission_id = ? ORDER BY id",
        (submission_id,),
    )

    st.subheader("Line Item Review Details")

    for item in items:
        show_line_item(item)


def policy_chat(policies: PolicyLibrary) -> None:
    st.markdown('<div class="section-title">Ask the Policy Library</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-caption">Ask reimbursement and expense questions with grounded policy citations.</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="glass-card">', unsafe_allow_html=True)

    question = st.text_input("Ask a reimbursement or policy question")
    ask_clicked = st.button("Ask", disabled=not question.strip())

    st.markdown("</div>", unsafe_allow_html=True)

    if ask_clicked:
        answer = policies.answer_question(question)

        metric_card("Answer Confidence", f"{answer['confidence'] * 100:.0f}%", "#6366f1")

        st.write(answer["answer"])

        if answer["citations"]:
            st.subheader("Citations")
            for citation in answer["citations"]:
                st.markdown(f"**{citation['document']}**")
                st.info(citation["quote"])


def dashboard() -> None:
    st.markdown('<div class="section-title">📊 Executive Review Dashboard</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-caption">Finance analytics dashboard for expenses, policy risk, compliance, and audit activity.</div>',
        unsafe_allow_html=True,
    )

    total_submissions = rows("SELECT COUNT(*) AS count FROM submissions")[0]["count"]
    total_items = rows("SELECT COUNT(*) AS count FROM line_items")[0]["count"]
    total_amount = rows("SELECT COALESCE(SUM(amount), 0) AS total FROM line_items")[0]["total"]

    compliant_count = rows("SELECT COUNT(*) AS count FROM line_items WHERE verdict = 'Compliant'")[0]["count"]
    flagged_count = rows("SELECT COUNT(*) AS count FROM line_items WHERE verdict = 'Flagged'")[0]["count"]
    rejected_count = rows("SELECT COUNT(*) AS count FROM line_items WHERE verdict = 'Rejected'")[0]["count"]
    review_count = rows("SELECT COUNT(*) AS count FROM line_items WHERE verdict = 'Needs Human Review'")[0]["count"]

    compliance_rate = round((compliant_count / total_items) * 100, 1) if total_items else 0

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        metric_card("Submissions", str(total_submissions), "#6366f1")
    with col2:
        metric_card("Receipts", str(total_items), "#8b5cf6")
    with col3:
        metric_card("Total Spend", f"${total_amount:,.2f}", "#0ea5e9")
    with col4:
        metric_card("Compliance", f"{compliance_rate}%", "#22c55e")
    with col5:
        metric_card("Flagged", str(flagged_count), "#f59e0b")
    with col6:
        metric_card("Rejected", str(rejected_count), "#ef4444")

    if total_items == 0:
        st.info("No expense reviews yet. Go to New Review and upload receipts.")
        return

    st.divider()

    left, right = st.columns(2)

    with left:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("Verdict Distribution")

        verdict_data = rows("""
            SELECT verdict, COUNT(*) AS count
            FROM line_items
            GROUP BY verdict
            ORDER BY count DESC
        """)

        verdict_df = pd.DataFrame([dict(r) for r in verdict_data])

        fig = px.pie(
            verdict_df,
            names="verdict",
            values="count",
            hole=0.48,
            title="Policy Review Status",
            color="verdict",
            color_discrete_map={
                "Compliant": "#22c55e",
                "Flagged": "#f59e0b",
                "Rejected": "#ef4444",
                "Needs Human Review": "#3b82f6",
            },
        )

        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(height=420)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("Expense Category Breakdown")

        category_data = rows("""
            SELECT COALESCE(category, 'Unknown') AS category, COUNT(*) AS count
            FROM line_items
            GROUP BY category
            ORDER BY count DESC
        """)

        category_df = pd.DataFrame([dict(r) for r in category_data])

        fig = px.bar(
            category_df,
            x="category",
            y="count",
            color="category",
            title="Receipt Count by Category",
            text="count",
        )

        fig.update_layout(showlegend=False, height=420)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    left, right = st.columns(2)

    with left:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("Spend by Category")

        spend_category = rows("""
            SELECT COALESCE(category, 'Unknown') AS category,
                   COALESCE(SUM(amount), 0) AS total_amount
            FROM line_items
            GROUP BY category
            ORDER BY total_amount DESC
        """)

        spend_category_df = pd.DataFrame([dict(r) for r in spend_category])

        fig = px.treemap(
            spend_category_df,
            path=["category"],
            values="total_amount",
            title="Expense Share by Category",
        )

        fig.update_layout(height=430)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("Top Employees by Spend")

        employee_spend = rows("""
            SELECT e.name AS employee,
                   COALESCE(SUM(l.amount), 0) AS total_amount
            FROM employees e
            JOIN submissions s ON e.id = s.employee_id
            JOIN line_items l ON s.id = l.submission_id
            GROUP BY e.name
            ORDER BY total_amount DESC
            LIMIT 10
        """)

        employee_spend_df = pd.DataFrame([dict(r) for r in employee_spend])

        fig = px.bar(
            employee_spend_df,
            x="total_amount",
            y="employee",
            orientation="h",
            color="total_amount",
            title="Highest Spending Employees",
            text="total_amount",
        )

        fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=430)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    left, right = st.columns(2)

    with left:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("Confidence Score Analysis")

        confidence_data = rows("""
            SELECT verdict, ROUND(AVG(confidence) * 100, 2) AS avg_confidence
            FROM line_items
            GROUP BY verdict
        """)

        confidence_df = pd.DataFrame([dict(r) for r in confidence_data])

        fig = px.line(
            confidence_df,
            x="verdict",
            y="avg_confidence",
            markers=True,
            title="Average AI Confidence by Verdict",
        )

        fig.update_layout(height=420)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("Department Spend")

        dept_data = rows("""
            SELECT e.department,
                   COALESCE(SUM(l.amount), 0) AS total_amount
            FROM employees e
            JOIN submissions s ON e.id = s.employee_id
            JOIN line_items l ON s.id = l.submission_id
            GROUP BY e.department
            ORDER BY total_amount DESC
        """)

        dept_df = pd.DataFrame([dict(r) for r in dept_data])

        fig = px.pie(
            dept_df,
            names="department",
            values="total_amount",
            title="Spend by Department",
        )

        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(height=420)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.divider()

    st.subheader("Recent Expense Reviews")

    recent_reviews = rows("""
        SELECT 
            s.created_at,
            e.name AS employee,
            e.department,
            l.vendor,
            l.category,
            l.amount,
            l.verdict,
            l.confidence
        FROM line_items l
        JOIN submissions s ON s.id = l.submission_id
        JOIN employees e ON e.id = s.employee_id
        ORDER BY s.created_at DESC
        LIMIT 10
    """)

    recent_df = pd.DataFrame([dict(r) for r in recent_reviews])

    if not recent_df.empty:
        recent_df["amount"] = recent_df["amount"].apply(lambda x: f"${x:,.2f}" if x else "$0.00")
        recent_df["confidence"] = recent_df["confidence"].apply(lambda x: f"{x * 100:.0f}%" if x else "0%")
        st.dataframe(recent_df, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("🤖 AI Risk Insights")

    if compliance_rate >= 80:
        st.success("Overall compliance is strong. Most receipts are matching company policy.")
    elif compliance_rate >= 50:
        st.warning("Compliance is moderate. Finance team should review flagged categories.")
    else:
        st.error("Compliance is low. Manual audit is recommended before reimbursement.")

    if flagged_count:
        st.warning(f"{flagged_count} receipt(s) are flagged and need finance review.")

    if rejected_count:
        st.error(f"{rejected_count} receipt(s) are rejected and should not be reimbursed without approval.")

    if review_count:
        st.info(f"{review_count} receipt(s) require human review due to uncertainty.")

    st.divider()

    st.subheader("Manager Override Audit Trail")

    override_data = rows("""
        SELECT 
            o.created_at,
            l.filename,
            l.vendor,
            l.verdict AS original_verdict,
            o.new_verdict,
            o.comment
        FROM overrides o
        JOIN line_items l ON l.id = o.line_item_id
        ORDER BY o.created_at DESC
        LIMIT 10
    """)

    override_df = pd.DataFrame([dict(r) for r in override_data])

    if not override_df.empty:
        st.dataframe(override_df, use_container_width=True, hide_index=True)
    else:
        st.info("No manager overrides recorded yet.")


def main() -> None:
    bootstrap()
    policies = get_policy_library()

    with st.sidebar:
        st.markdown("## 🚚 Northwind AI")
        st.markdown("Expense Policy Reviewer")
        st.divider()

        page = st.radio(
            "Navigation",
            ["Dashboard", "New Review", "History", "Policy Q&A"],
        )

        st.divider()
        st.caption("Built for AI-assisted finance review")

    app_header()

    if page == "Dashboard":
        dashboard()
    elif page == "New Review":
        submission_builder(policies)
    elif page == "History":
        history_view()
    else:
        policy_chat(policies)


if __name__ == "__main__":
    main()