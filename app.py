import streamlit as st
import pandas as pd
from pathlib import Path

st.title("Renewable Energy PhD Radar")

file=Path("reports/latest_matches.csv")

if file.exists():
    df=pd.read_csv(file)
    st.dataframe(df,use_container_width=True)

else:
    st.info("Run worker.py first.")
