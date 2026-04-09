
import io
import pandas as pd
import numpy as np
import streamlit as st

st.set_page_config(page_title="SEO Tracker", layout="wide")

DEFAULT_NO_RANK = 100

def detect_and_transform(df):
    # Detect long format
    if "Start Date" in df.columns and "Keyword" in df.columns:
        df = df.copy()
        df["Month"] = pd.to_datetime(df["Start Date"]).dt.strftime("%Y-%m")

        rank_col = "Google"
        if "Google Base Rank" in df.columns:
            rank_col = "Google Base Rank"

        df = df[["Keyword", "Month", rank_col]].rename(columns={rank_col: "Rank"})

        df = df.pivot_table(
            index="Keyword",
            columns="Month",
            values="Rank",
            aggfunc="min"
        ).reset_index()

    return df

def clean(df):
    keyword_col = df.columns[0]
    month_cols = df.columns[1:]

    for col in month_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df.loc[df[col] <= 0, col] = np.nan

    return df, keyword_col, list(month_cols)

def summary(df, keyword_col, month_cols, no_rank):
    rows = []

    for col in month_cols:
        s = df[col]

        if s.notna().sum() == 0:
            continue

        total = len(df)
        ranked = s.notna().sum()

        effective = s.fillna(no_rank)

        rows.append({
            "Month": col,
            "Visibility %": round((ranked/total)*100,2),
            "Avg rank (incl no-rank)": round(effective.mean(),2),
            "Top 10": int(((s>=1)&(s<=10)).sum())
        })

    return pd.DataFrame(rows)

st.title("SEO Monthly Tracker")

no_rank = st.sidebar.number_input("No-rank value", value=DEFAULT_NO_RANK)

file = st.file_uploader("Upload file", type=["csv","xlsx"])

if file:
    if file.name.endswith(".csv"):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file)

    df = detect_and_transform(df)
    df, keyword_col, months = clean(df)

    summ = summary(df, keyword_col, months, no_rank)

    st.subheader("Summary")
    st.dataframe(summ)

    st.line_chart(summ.set_index("Month"))

    st.subheader("Raw data")
    st.dataframe(df)
