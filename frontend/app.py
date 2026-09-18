import streamlit as st
import requests
import pandas as pd

# Update with your actual FastAPI service URLs
FASTAPI_UPLOAD_URL = "http://localhost:8000/bills/upload"
FASTAPI_BILLS_URL = "http://localhost:8000/bills"
FASTAPI_REVIEW_BILLS_URL = "http://localhost:8000/bills/review"

st.set_page_config(layout="wide")
st.title("🧾 Bill Processing Pipeline (Groq AI)")

# Create separate views for your workflow
tab_upload, tab_review = st.tabs(
    ["🚀 Upload & Parse Bill", "🔍 Review & Approve Expenses"])

# --- TAB 1: UPLOAD & AUTOMATIC PARSING ---
with tab_upload:
    st.subheader("Upload Bill Image")
    uploaded_file = st.file_uploader(
        "Choose a receipt or bill photo...", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        st.image(uploaded_file, caption="Uploaded Document", width=300)

        if st.button("Extract Data with Groq"):
            with st.spinner("Groq API is reading the bill..."):
                # Forward file payload to FastAPI backend
                files = {
                    "file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                response = requests.post(FASTAPI_UPLOAD_URL, files=files)

                if response.status_code == 200:
                    parsed_data = response.json()
                    st.success(
                        "Successfully parsed! Head over to the 'Review & Approve' tab to verify.")
                    # Visual confirmation of raw AI output
                    st.json(parsed_data)
                else:
                    st.error(f"Backend processing failed: {response.text}")

# --- TAB 2: REVIEW AND INLINE EDITING ---
with tab_review:
    st.subheader("Pending & Logged Expenses")

    # Fetch all bills from the backend
    res = requests.get(FASTAPI_REVIEW_BILLS_URL)
    if res.status_code == 200 and res.json():
        all_bills = res.json()
        df = pd.DataFrame(all_bills)

        df["bill_date"] = pd.to_datetime(df["bill_date"]).dt.date
        df["extracted_at"] = pd.to_datetime(df["extracted_at"])
        if "reviewed_at" in df.columns:
            df["reviewed_at"] = pd.to_datetime(df["reviewed_at"])

        st.write(
            "Double-click any cell below to fix AI parsing mistakes, then click **Save Changes**.")

        # --- ADD THIS INSIDE TAB_REVIEW, ABOVE THE DATA EDITOR ---
    if not df.empty:
        st.markdown("### 📊 Monthly Financial Overviews")

        # Create temporary helper columns for grouping
        # Convert dates to a clean 'YYYY-MM' string format
        df_metrics = df.copy()
        df_metrics["Month"] = pd.to_datetime(
            df_metrics["bill_date"]).dt.strftime("%Y-%m")

        # Filter for approved bills only (or include everything depending on preference)
        approved_only = df_metrics[df_metrics["status"] == "approved"]

        if not approved_only.empty:
            # 1. Total Spending per Month
            monthly_totals = approved_only.groupby(
                "Month")["total_amount"].sum().reset_index()

            # 2. Total Spending per Category per Month
            categorical_totals = approved_only.groupby(["Month", "category"])[
                "total_amount"].sum().reset_index()

            # Display the summaries using clean markdown layouts or metrics
            col_monthly, col_category = st.columns(2)

            with col_monthly:
                st.markdown("**Total Approved Expenses by Month:**")
                # Displays a quick scannable summary table
                st.dataframe(
                    monthly_totals.rename(
                        columns={"total_amount": "Total ($)"}),
                    hide_index=True,
                    width="stretch"
                )

            with col_category:
                st.markdown("**Breakdown by Category:**")
                st.dataframe(
                    categorical_totals.rename(
                        columns={"total_amount": "Total ($)"}),
                    hide_index=True,
                    width="stretch"
                )
        else:
            st.info(
                "💡 Tip: Set a bill's status to **approved** and sync to see data reflected in monthly overviews.")

        st.divider()  # Adds a clean separation line before the main editable grid
    # ---------------------------------------------------------

        # st.data_editor creates a fully interactive CRUD spreadsheet UI
        edited_df = st.data_editor(
            df,
            key="bill_editor",
            num_rows="dynamic",
            # Don't allow changing structural DB metadata
            disabled=["id"],
            column_config={
                "id": st.column_config.NumberColumn("DB ID"),
                "bill_date": st.column_config.DateColumn("Bill Date", required=True),
                "vendor_name": st.column_config.TextColumn("Vendor Name", required=True),
                "total_amount": st.column_config.NumberColumn("Total Amount ($)", min_value=0.0, format="$%.2f", required=True),

                # 1. Dropdown Column for Category
                "category": st.column_config.SelectboxColumn(
                    "Category",
                    options=["Utilities", "Groceries", "Miscellaneous"],
                    required=True
                ),

                # 2. Dropdown Column for Status
                "status": st.column_config.SelectboxColumn(
                    "Status Options",
                    options=["pending", "approved", "rejected"],
                    required=True
                ),

                "extracted_at": st.column_config.DatetimeColumn("AI Extraction Time"),
                "reviewed_at": st.column_config.DatetimeColumn("Last Processed Time"),
                "reviewer_comment": st.column_config.TextColumn("Reviewer Comments")
            }
        )

        # Check for user edits in the data grid
        if st.button("Save & Sync Changes to DB"):
            # Determine rows that changed by comparing dataframes
            # Alternatively, extract session state changes to map specific PUT requests
            success_count = 0

            for index, row in edited_df.iterrows():
                bill_id = row.get("id")
                # Format payload matching your SQLModel schema requirements
                payload = {
                    "bill_date": row["bill_date"].strftime("%Y-%m-%d"),
                    "vendor_name": str(row["vendor_name"]),
                    "total_amount": float(row["total_amount"]),
                    "category": str(row["category"]),
                    "status": str(row["status"]),
                    "reviewer_comment": str(row["reviewer_comment"]) if pd.notna(row["reviewer_comment"]) else None
                }

                # Send PUT request to update individual records
                put_res = requests.put(
                    f"{FASTAPI_BILLS_URL}/{bill_id}", json=payload)
                if put_res.status_code == 200:
                    success_count += 1

            if success_count > 0:
                st.success(
                    f"Successfully synchronized {success_count} records with backend!")
                st.rerun()

    else:
        st.info("No records found in the database. Upload a bill to populate.")
