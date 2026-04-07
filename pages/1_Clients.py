import streamlit as st
import json
from models.database import init_db, get_session, Client

init_db()

st.title("Client Management")

SECTORS = [
    "Retail", "Finance & Banking", "Insurance", "Healthcare", "Manufacturing",
    "Technology", "Telecom", "Energy & Utilities", "Public Sector",
    "Transportation & Logistics", "Media & Entertainment", "Real Estate",
    "Consulting & Services", "Education", "Agriculture", "Other",
]

SIZES = ["PME", "ETI", "GE"]

TECH_STACK_OPTIONS = {
    "ERP": ["SAP", "Oracle", "Microsoft Dynamics", "Odoo", "Sage", "Other ERP"],
    "CRM": ["Salesforce", "HubSpot", "Microsoft Dynamics CRM", "Zoho", "Other CRM"],
    "Cloud": ["AWS", "Azure", "GCP", "OVH", "On-premise only"],
    "Data": ["Snowflake", "Databricks", "BigQuery", "Redshift", "PostgreSQL", "MongoDB", "Other DB"],
    "BI": ["Power BI", "Tableau", "Looker", "Qlik", "Metabase", "Other BI"],
    "ML/AI": ["Dataiku", "SageMaker", "Vertex AI", "MLflow", "Hugging Face", "OpenAI API", "Custom Python"],
}

# --- Create new client ---
st.subheader("Add New Client")
with st.form("new_client_form"):
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Company Name*")
        sector = st.selectbox("Sector", SECTORS)
    with col2:
        size = st.selectbox("Company Size", SIZES)
        country = st.text_input("Country", value="France")

    st.markdown("**Tech Stack**")
    selected_stack = []
    cols = st.columns(3)
    for i, (category, tools) in enumerate(TECH_STACK_OPTIONS.items()):
        with cols[i % 3]:
            chosen = st.multiselect(category, tools, key=f"stack_{category}")
            selected_stack.extend(chosen)

    submitted = st.form_submit_button("Create Client")
    if submitted:
        if not name.strip():
            st.error("Company name is required.")
        else:
            session = get_session()
            try:
                client = Client(
                    name=name.strip(),
                    sector=sector,
                    size=size,
                    country=country,
                    tech_stack=json.dumps(selected_stack),
                )
                session.add(client)
                session.commit()
                st.success(f"Client '{name}' created successfully!")
                st.rerun()
            finally:
                session.close()

st.divider()

# --- List existing clients ---
st.subheader("Existing Clients")
session = get_session()
try:
    clients = session.query(Client).order_by(Client.created_at.desc()).all()
    clients_data = []
    for c in clients:
        clients_data.append({
            "id": c.id,
            "name": c.name,
            "sector": c.sector,
            "size": c.size,
            "country": c.country,
            "tech_stack": c.get_tech_stack(),
            "created": str(c.created_at)[:10] if c.created_at else "",
        })
finally:
    session.close()

if not clients_data:
    st.info("No clients yet. Create one above.")
else:
    for c in clients_data:
        with st.expander(f"🏢 {c['name']} — {c['sector']} — {c['size']}"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Country:** {c['country']}")
                st.write(f"**Created:** {c['created']}")
            with col2:
                if c["tech_stack"]:
                    st.write(f"**Tech Stack:** {', '.join(c['tech_stack'])}")
                else:
                    st.write("**Tech Stack:** Not specified")

            if st.button(f"Delete", key=f"del_{c['id']}"):
                session = get_session()
                try:
                    client = session.query(Client).get(c["id"])
                    if client:
                        session.delete(client)
                        session.commit()
                        st.success(f"Client '{c['name']}' deleted.")
                        st.rerun()
                finally:
                    session.close()
