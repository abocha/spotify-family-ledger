import streamlit as st

st.set_page_config(page_title="Spotify Family Ledger", layout="wide")

st.title("🛰️ Spotify Family Ledger")

# Simple navigation mock
page = st.sidebar.selectbox("Navigation", ["Home", "Members", "Post Cycle", "Record Payment", "History", "Export"])

if page == "Home":
    st.header("Dashboard")
    st.info("Welcome to the ledger. Check the sidebar to navigate.")
    
elif page == "Members":
    st.header("Members")
    st.write("Member list and balance overview will go here.")

elif page == "Post Cycle":
    st.header("Post Cycle")
    st.write("Review and confirm the next billing cycle.")

elif page == "Record Payment":
    st.header("Record Payment")
    st.write("Input member payments here.")

elif page == "History":
    st.header("History")
    st.write("Immutable record of cycles and payments.")

elif page == "Export":
    st.header("Export")
    st.write("Generate Excel/CSV reports.")
