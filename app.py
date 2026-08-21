import streamlit as st
import pandas as pd

st.title("Renewable Energy PhD Radar v12")

try:
    df=pd.read_csv("reports/opportunities.csv")
    st.dataframe(df,use_container_width=True)
except:
    st.info("Run worker.py")
