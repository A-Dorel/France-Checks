import streamlit as st
import polars as pl
from streamlit_agraph import agraph, Node, Edge, Config

from functions import get_companies, get_company_info, get_pcl_record, remove_accents, to_upper_no_accents
from models import FranceCompany

st.set_page_config(
    page_title="France Checks",
    page_icon=":mag:",
)

nodes = []
edges = []

if "search_result" not in st.session_state:
    st.session_state.search_result = None
if "search_pcl" not in st.session_state:
    st.session_state.search_pcl = None
if "graph_companies" not in st.session_state:
    st.session_state.graph_companies = None
if "search_first_name" not in st.session_state:
    st.session_state.search_first_name = ""
if "search_last_name" not in st.session_state:
    st.session_state.search_last_name = ""

st.title(":mag: France Checks")

st.text("This app checks the existence of a company in France based on the provided first and last name.")
st.warning(
    "This app does not perform exact matching on the First Name and Last Name, results given need to be carefully reviewed. The source used is BODACC.", 
    icon="⚠️"
)

col1, col2 = st.columns(2)

with col1:
    first_name = st.text_input("First Name")
with col2:
    last_name = st.text_input("Last Name")

if st.button("Check"):
    df = get_companies(first_name, last_name)

    companies = pl.DataFrame(schema=FranceCompany())
    companies = companies.cast(
        {
            "Siren": pl.String,
            "CompanyName": pl.String,
            "Sector": pl.String,
            "Address": pl.String,
            "CreationDate": pl.String,
            "Dirigeants": pl.String,
        }
    )

    pcl = pl.DataFrame(
        {
            "Siren": [],
            "CompanyName": [],
            "PublicationDate": [],
            "Nature": [],
            "Url": [],
            "Jugement_Type": [],
            "Jugement_Famille": [],
            "Jugement_Nature": [],
            "Jugement_Date": [],
            "Jugement_Complement": [],
        }
    )

    pcl = pcl.cast(
        {
            "Siren": pl.String,
            "CompanyName": pl.String,
            "PublicationDate": pl.String,
            "Nature": pl.String,
            "Url": pl.String,
            "Jugement_Type": pl.String,
            "Jugement_Famille": pl.String,
            "Jugement_Nature": pl.String,
            "Jugement_Date": pl.String,
            "Jugement_Complement": pl.String,
        }
    )

    for row in df.iter_rows(named=True):
        try:
            company_info = get_company_info(row['Siren'])

            if company_info.CompanyName is not None:
                companies = companies.vstack(pl.DataFrame([company_info.dict()]))

            try:
               print(f"Processing company: {row['Siren']}")
               if row['Siren'] is not None:
                   pcl_record = get_pcl_record(row['Siren'])
                   if not pcl_record.is_empty():
                       pcl = pcl.vstack(pcl_record)
            except Exception as e:
               print(f"Failed to get PCL record for {row['Siren']}: {e}")
        except Exception as e:
            print(f"Failed to get company info for {row['Siren']}: {e}")

    result = df.join(companies.drop("CompanyName"), on="Siren", how="left")
    name = f"{first_name} {last_name}"
    normalized_name = to_upper_no_accents(name)
    graph_companies = result.filter(
        pl.col("Dirigeants").str.contains(f"{normalized_name}", literal=True)
    )

    st.session_state.search_result = result
    st.session_state.search_pcl = pcl
    st.session_state.graph_companies = graph_companies
    st.session_state.search_first_name = first_name
    st.session_state.search_last_name = last_name

if st.session_state.search_result is not None:
    result = st.session_state.search_result
    pcl = st.session_state.search_pcl
    graph_companies = st.session_state.graph_companies
    selected_first_name = st.session_state.search_first_name
    selected_last_name = st.session_state.search_last_name

    if result.is_empty():
        st.warning("No company found.")
    else:
        st.success("Companies found:")
        st.dataframe(result)

        if not pcl.is_empty():
            st.subheader("Procedures Collectives Records:")
            st.dataframe(
                pcl
                .select(
                    [
                        pl.col("Siren"),
                        pl.col("CompanyName"),
                        pl.col("PublicationDate"),
                        pl.col("Jugement_Nature"),
                        pl.col("Jugement_Date"),
                        pl.col("Jugement_Complement"),
                        pl.col("Url"),
                    ]
                )
            )
        else:
            st.info("No Procedures Collectives records found for the company.")

    st.markdown("###### Graph Representation (only showing companies with matching director):")
    nodes = []
    edges = []

    nodes.append(
        Node(
            id="Person",
            label=f"{selected_first_name} {selected_last_name}",
            size=25,
            font={"color": "black"},
            image="https://raw.githubusercontent.com/material-icons/material-icons-png/refs/heads/master/png/white/person/baseline-2x.png",
            shape="circularImage",
        )
    )

    for row in graph_companies.unique(subset="Siren", keep="first", maintain_order=True).iter_rows(named=True):
        is_pcl = pcl.select(pl.col("Siren").is_in([row["Siren"]]).any()).item()
        color = "red" if is_pcl else "green"
        nodes.append(
            Node(
                id=f"{row['Siren']}",
                label=row["CompanyName"],
                color=color,
                font={"color": "black"},
                size=25,
                link=f"https://www.pappers.fr/entreprise/{row['Siren']}",
                image="https://raw.githubusercontent.com/material-icons/material-icons-png/refs/heads/master/png/white/business/baseline-2x.png",
                shape="circularImage",
            )
        )
        edges.append(
            Edge(
                source="Person",
                target=f"{row['Siren']}",
            )
        )

    config = Config(
        width=700,
        height=500,
        directed=True,
        physics=False,
        hierarchical=False,
        highlightColor="#F0F0F0",
        nodeHighlightBehavior=True,
    )

    return_value = agraph(
        nodes=nodes,
        edges=edges,
        config=config,
    )
    

