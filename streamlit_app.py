import requests
import streamlit as st

API_BASE_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="AI Support Ticket Assistant", layout="centered")


# ---------- Session state ----------

if "token" not in st.session_state:
    st.session_state.token = None
if "email" not in st.session_state:
    st.session_state.email = None


def is_logged_in() -> bool:
    return st.session_state.token is not None


def auth_headers() -> dict:
    return {"Authorization": f"Bearer {st.session_state.token}"}


def logout():
    st.session_state.token = None
    st.session_state.email = None


# ---------- API helpers ----------

def register(email: str, password: str):
    return requests.post(
        f"{API_BASE_URL}/register",
        json={"email": email, "password": password},
    )


def login(email: str, password: str):
    return requests.post(
        f"{API_BASE_URL}/login",
        json={"email": email, "password": password},
    )


def create_ticket(message: str):
    return requests.post(
        f"{API_BASE_URL}/tickets",
        json={"message": message},
        headers=auth_headers(),
    )


def get_tickets():
    return requests.get(f"{API_BASE_URL}/tickets", headers=auth_headers())


def get_ticket(ticket_id: int):
    return requests.get(f"{API_BASE_URL}/tickets/{ticket_id}", headers=auth_headers())


# ---------- Pages ----------

def page_login_register():
    st.title("AI Support Ticket Assistant")

    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Login")

            if submitted:
                if not email or not password:
                    st.error("Please enter both email and password.")
                else:
                    response = login(email, password)
                    if response.status_code == 200:
                        st.session_state.token = response.json()["access_token"]
                        st.session_state.email = email
                        st.rerun()
                    else:
                        detail = response.json().get("detail", "Login failed")
                        st.error(detail)

    with tab_register:
        with st.form("register_form"):
            email = st.text_input("Email", key="register_email")
            password = st.text_input(
                "Password (min 8 characters)", type="password", key="register_password"
            )
            submitted = st.form_submit_button("Register")

            if submitted:
                if not email or not password:
                    st.error("Please enter both email and password.")
                else:
                    response = register(email, password)
                    if response.status_code == 201:
                        st.success("Account created! You can now log in.")
                    else:
                        detail = response.json().get("detail", "Registration failed")
                        st.error(detail)


def render_decision(decision: dict):
    action = decision["action"]
    confidence = decision["confidence"]
    reason = decision["reason"]
    sources = decision["sources"]

    action_colors = {
        "APPROVE_REFUND": "green",
        "APPROVE_REPLACEMENT": "green",
        "REQUEST_PHOTOS": "orange",
        "DENY": "red",
        "ESCALATE": "red",
        "NEEDS_MORE_INFORMATION": "gray",
    }
    color = action_colors.get(action, "blue")

    st.markdown(f"**Action:** :{color}[{action}]")
    st.progress(confidence, text=f"Confidence: {confidence:.0%}")
    st.markdown(f"**Reason:** {reason}")
    st.markdown(f"**Sources:** {', '.join(sources) if sources else 'None'}")


def page_new_decision():
    st.header("Submit a Support Ticket")

    with st.form("ticket_form"):
        message = st.text_area(
            "Describe your issue",
            placeholder="e.g. My order arrived damaged. It cost around 3000 rupees. What should I do?",
            height=120,
        )
        submitted = st.form_submit_button("Get Decision")

    if submitted:
        if not message.strip():
            st.error("Please enter a message.")
        else:
            with st.spinner("Analyzing your ticket..."):
                response = create_ticket(message)

            if response.status_code == 201:
                ticket = response.json()
                st.success("Decision generated!")
                st.subheader("Result")
                if ticket.get("decision"):
                    render_decision(ticket["decision"])
                else:
                    st.warning("No decision was generated for this ticket.")
            else:
                detail = response.json().get("detail", "Failed to create ticket")
                st.error(detail)


def page_history():
    st.header("Your Ticket History")

    response = get_tickets()
    if response.status_code != 200:
        st.error("Failed to load ticket history.")
        return

    tickets = response.json()
    if not tickets:
        st.info("You haven't submitted any tickets yet.")
        return

    for ticket in tickets:
        with st.expander(f"#{ticket['id']} — {ticket['message'][:60]}..."):
            st.markdown(f"**Full message:** {ticket['message']}")
            st.markdown(f"**Submitted:** {ticket['created_at']}")
            if ticket.get("decision"):
                st.markdown("---")
                render_decision(ticket["decision"])
            else:
                st.info("No decision available for this ticket.")


# ---------- Main app ----------

def main():
    if not is_logged_in():
        page_login_register()
        return

    st.sidebar.title("AI Support Ticket Assistant")
    st.sidebar.markdown(f"Logged in as **{st.session_state.email}**")

    page = st.sidebar.radio("Navigate", ["New Decision", "History"])

    if st.sidebar.button("Logout"):
        logout()
        st.rerun()

    if page == "New Decision":
        page_new_decision()
    elif page == "History":
        page_history()


if __name__ == "__main__":
    main()