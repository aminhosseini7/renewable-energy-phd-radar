import streamlit as st
import pandas as pd

st.title("Renewable Energy PhD Radar")

try:
    st.dataframe(pd.read_csv("reports/opportunities.csv"))
except:
    st.info("Run worker.py first")
