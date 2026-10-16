import streamlit as st
import requests
import pandas as pd

# Configure your FastAPI backend base URL
API_BASE_URL = "http://localhost:8000/accounts"  # Update with your actual FastAPI URL

def render_bank_statement_upload_tab():
    st.header("🏦 Bank Statement Upload & Review")
    st.markdown("Upload a PDF bank statement. Transactions will be parsed, saved as pending, and displayed below for your review.")

    # Fetch accounts for dropdown
    try:
        accounts_res = requests.get(f"{API_BASE_URL}")
        account_options = {acc["name"]: acc["id"] for acc in accounts_res.json()} if accounts_res.status_code == 200 else {"Default": 1}
    except Exception:
        account_options = {"Default Checking Account": 1}

    selected_account = st.selectbox("Select Account", options=list(account_options.keys()))
    account_id = account_options[selected_account]

    uploaded_pdf = st.file_uploader("Upload PDF Statement", type=["pdf"])

    if uploaded_pdf is not None:
        if st.button("Upload & Process Statement", type="primary"):
            with st.spinner("Parsing PDF and saving transactions..."):
                files = {"file": (uploaded_pdf.name, uploaded_pdf.getvalue(), "application/pdf")}
                try:
                    response = requests.post(f"{API_BASE_URL}/upload-statement/{account_id}", files=files)
                    
                    if response.status_code in [200, 201]:
                        data = response.json()
                        st.success(f"Successfully imported {data['transactions_imported_count']} transactions!")
                        # Store the returned transactions in session state for validation
                        st.session_state["review_transactions"] = data.get("transactions", [])
                    else:
                        st.error(f"Error: {response.text}")
                except Exception as e:
                    st.error(f"Connection failed: {e}")

    # Render review/validation grid if transactions exist in session state
    if "review_transactions" in st.session_state and st.session_state["review_transactions"]:
        st.subheader("Validate Imported Transactions")
        st.markdown("Make any necessary adjustments below:")

        df_review = pd.DataFrame(st.session_state["review_transactions"])
        edited_df = st.data_editor(df_review, num_rows="dynamic", width='stretch', key="tx_review_grid")

        if st.button("💾 Confirm & Save Changes"):
            # Optional sync call if user edited items inline
            updated_payload = {"transactions": edited_df.to_dict(orient="records")}
            try:
                sync_res = requests.put(f"{API_BASE_URL}/{account_id}/transactions/batch", json=updated_payload)
                if sync_res.status_code in [200, 201]:
                    st.success("Transactions updated successfully!")
                    del st.session_state["review_transactions"]
                    st.rerun()
                else:
                    st.error(f"Failed to update: {sync_res.text}")
            except Exception as e:
                st.error(f"Sync error: {e}")