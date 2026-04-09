import io
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="SEO Keyword Rank Tracker",
    page_icon="📈",
    layout="wide",
)


DEFAULT_NO_RANK_VALUE = 100
DEFAULT_TEMPLATE_ROWS = 400


def clean_positions(df: pd.DataFrame, keyword_col: str, month_cols: list[str]) -> pd.DataFrame:
    data = df.copy()
    data[keyword_col] = data[keyword_col].astype(str).str.strip()

    for col in month_cols:
        # Keep blanks as NaN = no rank
        data[col] = pd.to_numeric(data[col], errors="coerce")
        data.loc[data[col] <= 0, col] = np.nan

    return data


def monthly_summary(df: pd.DataFrame, keyword_col: str, month_cols: list[str], no_rank_value: int) -> pd.DataFrame:
    rows = []

    for col in month_cols:
        s = pd.to_numeric(df[col], errors="coerce")
        tracked_keywords = len(df)
        ranked = int(s.notna().sum())
        no_rank = int(s.isna().sum())

        effective = s.fillna(no_rank_value)

        rows.append(
            {
                "Month": col,
                "Tracked keywords": tracked_keywords,
                "Ranked keywords": ranked,
                "No-rank keywords": no_rank,
                "Visibility %": round((ranked / tracked_keywords) * 100, 2) if tracked_keywords else 0,
                "Average rank, ranked only": round(float(s.mean()), 2) if ranked else np.nan,
                f"Average rank, incl. no-rank={no_rank_value}": round(float(effective.mean()), 2) if tracked_keywords else np.nan,
                "Top 3": int(((s >= 1) & (s <= 3)).sum()),
                "Top 10": int(((s >= 1) & (s <= 10)).sum()),
                "Top 20": int(((s >= 1) & (s <= 20)).sum()),
                "Top 100": int(((s >= 1) & (s <= 100)).sum()),
            }
        )

    summary = pd.DataFrame(rows)

    if not summary.empty:
        summary["Visibility change vs prev"] = summary["Visibility %"].diff().round(2)
        incl_col = f"Average rank, incl. no-rank={no_rank_value}"
        summary["Avg rank change vs prev"] = summary[incl_col].diff().round(2)

    return summary


def build_template(month_names: list[str], rows: int = DEFAULT_TEMPLATE_ROWS) -> pd.DataFrame:
    cols = ["Keyword"] + month_names
    df = pd.DataFrame("", index=range(rows), columns=cols)
    df.index = df.index + 1
    return df


def to_excel_bytes(positions_df: pd.DataFrame, summary_df: pd.DataFrame, no_rank_value: int) -> bytes:
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        positions_df.to_excel(writer, sheet_name="Positions", index=False)
        summary_df.to_excel(writer, sheet_name="Summary", index=False)

        config_df = pd.DataFrame(
            {
                "Setting": ["No-rank value"],
                "Value": [no_rank_value],
            }
        )
        config_df.to_excel(writer, sheet_name="Config", index=False)

    output.seek(0)
    return output.getvalue()


def infer_month_columns(df: pd.DataFrame) -> tuple[str, list[str]]:
    if df.shape[1] < 2:
        raise ValueError("Filen måste ha minst två kolumner, en för keyword och minst en månadskolumn.")

    keyword_col = df.columns[0]
    month_cols = list(df.columns[1:])
    return keyword_col, month_cols


st.title("📈 SEO Keyword Rank Tracker")
st.caption("Ladda upp en CSV- eller Excel-fil och följ ranking, visibility och utveckling över tid.")

with st.sidebar:
    st.header("Inställningar")
    no_rank_value = st.number_input(
        "Värde för keywords som inte rankar",
        min_value=1,
        max_value=500,
        value=DEFAULT_NO_RANK_VALUE,
        step=1,
        help="Vanligt val är 50 eller 100. Det används när ett keyword saknar position.",
    )

    st.markdown("### Rekommenderat filformat")
    st.markdown(
        "- Första kolumnen = `Keyword`\n"
        "- Övriga kolumner = månader, till exempel `2026-01`, `2026-02`, `2026-03`\n"
        "- Lämna en cell tom om du inte rankar alls"
    )

    template_months = st.text_input(
        "Månader i mallfil",
        value="2026-01,2026-02,2026-03",
        help="Ange kommaseparerade månadsnamn för en tom mallfil.",
    )

uploaded = st.file_uploader(
    "Ladda upp rankingfil",
    type=["csv", "xlsx"],
    help="CSV eller Excel. Första kolumnen ska vara keyword, resten månadspositioner.",
)

col_a, col_b = st.columns([1, 1])

with col_a:
    month_names = [m.strip() for m in template_months.split(",") if m.strip()]
    if not month_names:
        month_names = ["2026-01", "2026-02", "2026-03"]

    template_df = build_template(month_names)
    template_csv = template_df.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        "⬇️ Ladda ner CSV-mall",
        data=template_csv,
        file_name="seo_keyword_template.csv",
        mime="text/csv",
    )

with col_b:
    example_df = pd.DataFrame(
        {
            "Keyword": ["seo byrå stockholm", "teknisk seo", "content audit"],
            "2026-01": [1, 4, None],
            "2026-02": [1, 3, 12],
            "2026-03": [2, None, 9],
        }
    )
    st.download_button(
        "⬇️ Ladda ner exempelfil",
        data=example_df.to_csv(index=False).encode("utf-8-sig"),
        file_name="seo_keyword_example.csv",
        mime="text/csv",
    )

if uploaded is None:
    st.info("Ladda upp en fil för att börja. Du kan använda mallfilen ovan.")
    st.stop()

try:
    if uploaded.name.lower().endswith(".csv"):
        raw_df = pd.read_csv(uploaded)
    else:
        raw_df = pd.read_excel(uploaded)
except Exception as e:
    st.error(f"Kunde inte läsa filen: {e}")
    st.stop()

try:
    keyword_col, month_cols = infer_month_columns(raw_df)
    data = clean_positions(raw_df, keyword_col, month_cols)
    data = data[data[keyword_col].notna()]
    data = data[data[keyword_col].astype(str).str.strip() != ""]
    summary = monthly_summary(data, keyword_col, month_cols, int(no_rank_value))
except Exception as e:
    st.error(f"Kunde inte tolka filen: {e}")
    st.stop()

st.subheader("Översikt")

if summary.empty:
    st.warning("Ingen användbar data hittades.")
    st.stop()

latest = summary.iloc[-1]
prev = summary.iloc[-2] if len(summary) > 1 else None
incl_col = f"Average rank, incl. no-rank={int(no_rank_value)}"

k1, k2, k3, k4 = st.columns(4)
k1.metric("Tracked keywords", int(latest["Tracked keywords"]))
k2.metric(
    "Visibility %",
    f'{latest["Visibility %"]:.2f}%',
    None if prev is None else f'{latest["Visibility %"] - prev["Visibility %"]:.2f} pp',
)
k3.metric(
    "Avg rank, incl. no-rank",
    f'{latest[incl_col]:.2f}',
    None if prev is None else f'{latest[incl_col] - prev[incl_col]:.2f}',
)
k4.metric(
    "Top 10",
    int(latest["Top 10"]),
    None if prev is None else int(latest["Top 10"] - prev["Top 10"]),
)

st.subheader("Månadsutveckling")
chart_option = st.selectbox(
    "Välj graf",
    options=[
        "Visibility %",
        incl_col,
        "Average rank, ranked only",
        "Top 10",
        "Top 3",
        "Top 20",
    ],
)
chart_df = summary.set_index("Month")[[chart_option]]
st.line_chart(chart_df)

c1, c2 = st.columns(2)

with c1:
    st.markdown("#### KPI-tabell")
    st.dataframe(summary, use_container_width=True)

with c2:
    st.markdown("#### Senaste månaden, fördelning")
    dist = pd.DataFrame(
        {
            "Bucket": ["Top 3", "Top 10", "Top 20", "Top 100", "No rank"],
            "Count": [
                int(latest["Top 3"]),
                int(latest["Top 10"]),
                int(latest["Top 20"]),
                int(latest["Top 100"]),
                int(latest["No-rank keywords"]),
            ],
        }
    )
    st.bar_chart(dist.set_index("Bucket"))

st.subheader("Positionsdata")
st.dataframe(data, use_container_width=True)

export_bytes = to_excel_bytes(data, summary, int(no_rank_value))
st.download_button(
    "⬇️ Ladda ner analys som Excel",
    data=export_bytes,
    file_name="seo_keyword_rank_analysis.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.markdown("---")
st.markdown(
    "**Hur appen räknar:** tom cell = ingen ranking. Då ersätts den med ditt valda `no-rank value`, "
    "till exempel 100, när `Avg rank, incl. no-rank` beräknas."
)
