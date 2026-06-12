# Northwind Logistics AI Expense Reviewer

## Overview

Northwind Logistics processes employee travel and expense reimbursements. Reviewing receipts manually against multiple policy documents is time-consuming and can lead to inconsistent decisions.

This project provides an AI-assisted expense review system that automatically analyzes receipts, checks compliance against company policies, generates review decisions, and supports human override workflows.

The solution helps finance teams review expenses faster while maintaining transparency, explainability, and auditability.

---

# Problem Statement

Finance reviewers need to determine whether submitted expenses comply with company reimbursement policies.

Challenges include:

* Large policy documents
* Different expense categories
* Missing or unclear receipt information
* Need for explainable decisions
* Requirement for audit trails

The goal is to assist reviewers rather than replace them.

---

# Features

## Employee Management

* Select existing employees
* Create new employees
* Store travel details
* Track department and grade information

## Receipt Processing

Supported formats:

* PDF
* PNG
* JPG
* WEBP
* TXT
* CSV

Extracted information:

* Vendor
* Amount
* Expense Category
* Receipt Text

## AI Expense Review

For each receipt, the system generates:

* Compliance Verdict
* Confidence Score
* Reasoning
* Policy Citations

Supported verdicts:

* Compliant
* Flagged
* Rejected
* Needs Human Review

## Policy Search & Q&A

Users can ask policy questions such as:

* Hotel reimbursement limits
* Meal reimbursement policies
* Travel documentation requirements

Answers are grounded using policy citations.

## Human Override Workflow

Finance reviewers can:

* Override AI decisions
* Add comments
* Maintain audit history

## Analytics Dashboard

Dashboard includes:

* Total Submissions
* Total Spend
* Compliance Rate
* Flagged Expenses
* Rejected Expenses
* Spend Analysis
* Department Analysis
* Employee Spend Analysis
* AI Confidence Metrics

## Submission History

Supports:

* Employee filtering
* Status filtering
* Date filtering
* Search functionality
* Review history lookup

---

# System Architecture

```text
User
 │
 ▼
Streamlit Dashboard
 │
 ├── Receipt Reader
 ├── Policy Engine
 ├── Review Engine
 └── SQLite Database
          │
          ▼
     Policy Retrieval
      (TF-IDF Search)
```

---

# Technology Stack

## Frontend

* Streamlit
* Plotly

## Backend

* Python

## AI / NLP

* Scikit-Learn
* TF-IDF Vectorizer
* Cosine Similarity

## Database

* SQLite

## Document Processing

* PyPDF

---

# Review Workflow

1. Select employee
2. Upload receipt
3. Extract receipt information
4. Retrieve relevant policies
5. Generate compliance verdict
6. Show reasoning and citations
7. Allow reviewer override
8. Store results for auditing

---

# Dashboard Metrics

The dashboard provides real-time insights:

### Executive KPIs

* Total Submissions
* Total Receipts
* Total Spend
* Compliance Percentage
* Flagged Expenses
* Rejected Expenses

### Visual Reports

* Verdict Distribution
* Expense Category Breakdown
* Spend by Category
* Department Spend
* Top Employees by Spend
* Confidence Score Analysis

### Audit Insights

* Override History
* Compliance Trends
* Risk Indicators

---

# Design Decisions

### Why Streamlit?

Streamlit allows rapid development of data-driven business applications with minimal frontend complexity.

### Why SQLite?

SQLite is lightweight, easy to deploy, and sufficient for the case study requirements.

### Why TF-IDF Search?

The policy library is relatively small, making TF-IDF a simple and efficient retrieval approach without requiring external vector databases.

### Why Human Review?

The system avoids making uncertain decisions and routes ambiguous cases to human reviewers.

---

# Evaluation Approach

An evaluation framework is included to measure:

* Verdict Accuracy
* Citation Quality
* Human Review Rate

Run evaluation:

```bash
python evals/evaluate.py evals/sample_expected.json
```

Output:

```text
evals/evaluation_report.json
```

---

# Running the Project

Clone repository:

```bash
git clone <repository-url>
cd northwind_expense_ai
```

Create virtual environment:

```bash
python -m venv venv
```

Activate environment:

Windows

```bash
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run application:

```bash
streamlit run app/main.py
```

---

# Future Improvements

Potential enhancements include:

* OCR using Azure Document Intelligence
* PostgreSQL database
* Role-based authentication
* Email notifications
* Approval workflows
* Fraud detection models
* Cloud deployment
* Vector database integration

---

# Conclusion

The Northwind Logistics AI Expense Reviewer streamlines expense auditing by combining receipt analysis, policy retrieval, explainable AI decisions, and human oversight. The solution improves review efficiency while maintaining transparency, compliance, and audit readiness.

This version is much cleaner, recruiter-friendly, and still covers the major requirements: **architecture, design decisions, dashboard, policy retrieval, human review, evaluation harness, scalability discussion, and setup instructions**.
