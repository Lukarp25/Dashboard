import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="AMC Holdings Dashboard", layout="wide")

# -------------------- Sticky Tabs CSS --------------------
st.markdown("""
<style>
div[data-testid="stTabs"] {
    position: sticky;
    top: 0;
    z-index: 999;
    background-color: white;
    padding-top: 10px;
}
button[data-baseweb="tab"] {
    font-weight: 700 !important;
    border: 1px solid #ddd !important;
    border-radius: 8px !important;
    margin-right: 6px !important;
    padding: 6px 12px !important;
    background-color: #f7f7f7 !important;
}
button[aria-selected="true"] {
    background-color: #4CAF50 !important;
    color: white !important;
}
</style>
""", unsafe_allow_html=True)
# -------------------- Load Data --------------------
@st.cache_data
def load_data():
    df = pd.read_excel("output/MIDCAP_master_holdings.xlsx")
    df.columns = df.columns.str.strip()

    df["Share Name"] = df["Share Name"].astype(str)
    df["Industry"] = df["Industry"].astype(str)
    df["ISIN"] = df["ISIN"].astype(str)
    
    df['%_to_NAV'] = pd.to_numeric(df['%_to_NAV'])

    amc_list = ['ABSL', 'AXIS', 'BANDHAN', 'BNP PARIBAS', 'BOI', 'DSP','EDELWEISS','HSBC','JM','ICICI', 'ITI', 'LIC', 'MIRAE ASSET',
                'MOTILAL', 'NIPPON', 'SUNDARAM','WHITEOAK']
                
    df['%_to_NAV'] = df.apply(
        lambda row: row['%_to_NAV'] * 100 if row['AMC'] in amc_list else row['%_to_NAV'],
        axis=1)

    df['%_to_NAV'] = df['%_to_NAV'].round(2)

    df.loc[df['AMC'] == 'UTI', 'Share Name'] = df.loc[df['AMC'] == 'UTI', 'Share Name'].str.replace('EQ - ', '', regex=False)

    df["Month_dt"] = df["Month"].apply(lambda x: datetime.strptime(x, "%b%y"))
    df = df.sort_values("Month_dt")

    return df

@st.cache_data
def create_master_isin(df):
    master = (
        df.sort_values("Month_dt")
        .groupby("ISIN")
        .agg({"Share Name": "first", "Industry": "first"})
        .reset_index()
    )
    return master

df = load_data()

isin_df = pd.read_excel("List of Corporate Actions.xlsx")
isin_map = dict(zip(isin_df['OLD ISIN'], isin_df['NEW ISIN']))
df['ISIN'] = df['ISIN'].replace(isin_map)

master_isin = create_master_isin(df)

# -------------------- Session State: Industry Filter --------------------
all_industries = sorted(master_isin["Industry"].unique())

if "industry_filter" not in st.session_state:
    st.session_state["industry_filter"] = all_industries

# -------------------- Sidebar --------------------
st.sidebar.header("Filters")

amc_filter = st.sidebar.multiselect(
    "Select AMC",
    options=sorted(df["AMC"].unique()),
    default=sorted(df["AMC"].unique())
)

share_filter = st.sidebar.multiselect(
    "Select Share",
    options=sorted(master_isin["Share Name"].unique()),
    default=sorted(master_isin["Share Name"].unique())
)

month_filter = st.sidebar.multiselect(
    "Select Month",
    options=sorted(df["Month"].unique(), key=lambda x: datetime.strptime(x, "%b%y"), reverse=True),
    default=sorted(df["Month"].unique(), key=lambda x: datetime.strptime(x, "%b%y"), reverse=True)
)

# Industry multiselect — driven by session state
industry_filter = st.sidebar.multiselect(
    "Select Industry",
    options=all_industries,
    default=st.session_state["industry_filter"],
    key="industry_multiselect"
)
# Sync session state back (handles manual sidebar edits)
st.session_state["industry_filter"] = industry_filter

# Reset button
if st.sidebar.button("🔄 Reset Industry Filter"):
    st.session_state["industry_filter"] = all_industries
    st.rerun()

selected_isins = master_isin[
    (master_isin["Share Name"].isin(share_filter)) &
    (master_isin["Industry"].isin(industry_filter))
]["ISIN"]

filtered_df = df[
    (df["AMC"].isin(amc_filter)) &
    (df["Month"].isin(month_filter)) &
    (df["ISIN"].isin(selected_isins))
].drop(columns=["Share Name", "Industry"])

# -------------------- Monthly Change --------------------
def calculate_monthly_change(data):
    data = data.sort_values(["AMC", "ISIN", "Month_dt"])
    data["Prev_Quantity"] = data.groupby(["AMC", "ISIN"])["Quantity"].shift(1)
    data["Change"] = data["Quantity"] - data["Prev_Quantity"]
    data["Per_Change"] = (data["Change"]/data["Prev_Quantity"])*100
    return data

change_df = calculate_monthly_change(filtered_df)

change_df = change_df.merge(master_isin, on="ISIN", how="left")
filtered_df = filtered_df.merge(master_isin, on="ISIN", how="left")

amc_list = sorted(change_df["AMC"].unique())

color_palette = (
    px.colors.qualitative.Bold +
    px.colors.qualitative.Vivid +
    px.colors.qualitative.Plotly
)

amc_color_map = {
    amc: color_palette[i % len(color_palette)]
    for i, amc in enumerate(amc_list)
}

# -------------------- Tabs --------------------
tab1, tab7, tab2, tab6, tab3, tab4, tab5,tab8 = st.tabs([
    "AMC Holdings",
    "Industry Flow",
    "Change in Holdings",
    "Stocks View",
    "Additions/Removals",
    "Most Bought/Sold",
    "Overlap",
    "Stocks to watch"
])

# =========================================================
# TAB 1 - AMC HOLDINGS
# =========================================================
with tab1:

    st.header("AMC Holdings by Share")

    top_n = st.slider("Select Top N Shares", 5, 50, 20)
    
    months_sorted = sorted(
        change_df["Month"].unique(),
        key=lambda x: datetime.strptime(x, "%b%y"),
        reverse=True
    )
    if len(months_sorted) == 0:
        st.warning("No data available for selected filters")
        st.stop()

    latest_month = months_sorted[0]

    selected_month_1 = st.selectbox(
        "Select Month for Analysis",
        months_sorted,
        index=months_sorted.index(latest_month), key="1"
    )

    holdings_df = (
        filtered_df[filtered_df["Month"] == selected_month_1]
        .groupby(["AMC", "ISIN", "Share Name", "Industry"])["%_to_NAV"]
        .sum()
        .reset_index()
        .sort_values("%_to_NAV", ascending=False)
    )

    fig0 = px.bar(
        holdings_df.head(top_n),
        x="Share Name",
        y="%_to_NAV",
        color="AMC",
        text="%_to_NAV",
        color_discrete_map=amc_color_map
    )

    fig0.update_traces(texttemplate='<b>%{text:.2f}%</b>', textposition="outside")
    fig0.update_layout(height=650, xaxis_tickangle=-45, title_font_size=22, font=dict(size=14))

    st.plotly_chart(fig0, width='stretch')

    st.header("AMC Holdings by Industry")

    holdings_df = (
        filtered_df[filtered_df["Month"] == selected_month_1]
        .groupby(["AMC", "Industry"])["%_to_NAV"]
        .sum()
        .reset_index()
        .sort_values("%_to_NAV", ascending=False)
    )

    fig3 = px.bar(
        holdings_df,
        x="Industry",
        y="%_to_NAV",
        color="AMC",
        text="%_to_NAV",
        color_discrete_map=amc_color_map
    )

    fig3.update_traces(texttemplate='<b>%{text:.2f}%</b>', textposition="outside")
    fig3.update_layout(height=650, xaxis_tickangle=-45, title_font_size=22, font=dict(size=14))

    st.plotly_chart(fig3, width='stretch')

# =========================================================
# TAB 2 - MONTHLY CHANGE
# =========================================================
with tab2:

    st.header("Monthly Change in Holding")

    col1, col2 = st.columns(2)

    with col1:
        month_1 = st.selectbox(
            "Select Base Month",
            months_sorted,
            index=1 if len(months_sorted) > 1 else 0,
            key="month1"
        )

    with col2:
        month_2 = st.selectbox(
            "Select Comparison Month",
            months_sorted,
            index=0,
            key="month2"
        )

    df_m1 = filtered_df[filtered_df["Month"] == month_1]
    df_m2 = filtered_df[filtered_df["Month"] == month_2]

    df_m1 = df_m1.groupby(["AMC", "ISIN"])["Quantity"].sum().reset_index()
    df_m2 = df_m2.groupby(["AMC", "ISIN"])["Quantity"].sum().reset_index()

    merged_df = pd.merge(
        df_m1, df_m2, on=["AMC", "ISIN"],
        how="outer", suffixes=("_m1", "_m2")
    ).fillna(0)

    merged_df["Change"] = merged_df["Quantity_m2"] - merged_df["Quantity_m1"]
    merged_df["Per_Change"] = merged_df.apply(
        lambda row: (row["Change"] / row["Quantity_m1"] * 100)
        if row["Quantity_m1"] != 0 else 0,
        axis=1
    )
    merged_df = merged_df.merge(master_isin, on="ISIN", how="left")

    st.subheader(f"Increase in Holdings ({month_1} → {month_2})")

    top_n_increase = st.slider("Select Top N Increases", 5, 50, 20, key="inc_slider")

    increase_df = merged_df[merged_df["Change"] > 0].sort_values("Per_Change", ascending=False)

    fig_inc = px.bar(
        increase_df.head(top_n_increase),
        x="Share Name", y="Per_Change", color="AMC", text="Per_Change",
        color_discrete_map=amc_color_map, title="Top Increases in Holdings (%)"
    )
    fig_inc.update_traces(texttemplate='<b>%{text:.2f}%</b>', textposition="outside")
    fig_inc.update_layout(height=650, xaxis_tickangle=-45, font=dict(size=14))
    st.plotly_chart(fig_inc, width='stretch')

    st.subheader(f"Decrease in Holdings ({month_1} → {month_2})")

    top_n_decrease = st.slider("Select Top N Decreases", 5, 50, 20, key="dec_slider")

    decrease_df = merged_df[merged_df["Change"] < 0].sort_values("Per_Change")

    fig_dec = px.bar(
        decrease_df.head(top_n_decrease),
        x="Share Name", y="Per_Change", color="AMC", text="Per_Change",
        color_discrete_map=amc_color_map, title="Top Decreases in Holdings (%)"
    )
    fig_dec.update_traces(texttemplate='<b>%{text:.2f}%</b>', textposition="outside")
    fig_dec.update_layout(height=650, xaxis_tickangle=-45, font=dict(size=14))
    st.plotly_chart(fig_dec, width='stretch')

# =========================================================
# TAB 6 - STOCKS VIEW
# =========================================================
with tab6:

    st.subheader("Stock Bought/Sold by AMC")

    selected_stock = st.selectbox(
        "Select Stock",
        sorted(change_df["Share Name"].unique())
    )

    selected_isin = master_isin[master_isin["Share Name"] == selected_stock]["ISIN"].values[0]

    view2_df = change_df[change_df["ISIN"] == selected_isin].sort_values(by=['Month_dt', 'AMC'])

    fig2 = px.bar(
        view2_df, x="Month", y="Per_Change", color="AMC", text="Per_Change",
        color_discrete_map=amc_color_map
    )
    fig2.update_traces(texttemplate='<b>%{text:.2f}%</b>', textposition="inside")
    fig2.update_layout(height=650, xaxis_tickangle=-45, font=dict(size=14))
    st.plotly_chart(fig2, width='stretch')

    st.subheader("Holding Trend")

    fig7 = px.line(
        view2_df, x="Month", y="Quantity", color="AMC",
        color_discrete_map=amc_color_map
    )
    fig7.update_traces(line=dict(width=3))
    st.plotly_chart(fig7, width='stretch')

# =========================================================
# TAB 3 - ADDITIONS / REMOVALS
# =========================================================
with tab3:

    months_sorted = sorted(
        change_df["Month"].unique(),
        key=lambda x: datetime.strptime(x, "%b%y"),
        reverse=True
    )
    if len(months_sorted) == 0:
        st.warning("No data available for selected filters")
        st.stop()

    latest_month = months_sorted[0]

    selected_month_2 = st.selectbox(
        "Select Month for Analysis",
        months_sorted,
        index=months_sorted.index(latest_month), key="2"
    )

    st.header("New Additions")

    new_additions = change_df[
        (change_df["Month"] == selected_month_2) &
        (change_df["Prev_Quantity"].isna())
    ]

    st.dataframe(new_additions[["AMC", "Share Name", "Industry", "Quantity", "%_to_NAV"]])

    st.header("Completely Removed Shares")

    months_sorted_df = (
        change_df[["Month", "Month_dt"]]
        .drop_duplicates()
        .sort_values("Month_dt")
    )

    current_month_dt = months_sorted_df[months_sorted_df["Month"] == selected_month_2]["Month_dt"].values[0]
    previous_month_row = months_sorted_df[months_sorted_df["Month_dt"] < current_month_dt]

    if not previous_month_row.empty:
        previous_month = previous_month_row.iloc[-1]["Month"]

        prev_month_df = change_df[change_df["Month"] == previous_month]
        curr_month_df = change_df[change_df["Month"] == selected_month_2]

        removed_isins = set(prev_month_df["ISIN"]) - set(curr_month_df["ISIN"])
        removed_df = prev_month_df[prev_month_df["ISIN"].isin(removed_isins)]

        st.dataframe(removed_df[["AMC", "Share Name", "Industry", "%_to_NAV"]])

# =========================================================
# TAB 4 - MOST BOUGHT / SOLD
# =========================================================
with tab4:

    months_sorted = sorted(
        change_df["Month"].unique(),
        key=lambda x: datetime.strptime(x, "%b%y"),
        reverse=True
    )
    if len(months_sorted) == 0:
        st.warning("No data available for selected filters")
        st.stop()

    latest_month = months_sorted[0]

    selected_month_3 = st.selectbox(
        "Select Month for Analysis",
        months_sorted,
        index=months_sorted.index(latest_month), key="3"
    )

    st.header("Most Bought and Sold Shares")

    view5_df = change_df[change_df["Month"] == selected_month_3]

    top_n = st.slider("Select Top N", 5, 50, 10, key="top_n_bought_sold")

    most_bought = view5_df.sort_values("Change", ascending=False).head(top_n)
    most_sold = view5_df.sort_values("Change").head(top_n)

    table_height = (top_n * 35) + 40

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top Bought")
        st.dataframe(most_bought[["Share Name", "AMC", "Change"]], height=table_height, width='stretch')

    with col2:
        st.subheader("Top Sold")
        st.dataframe(most_sold[["Share Name", "AMC", "Change"]], height=table_height, width='stretch')

# =========================================================
# TAB 5 - OVERLAP ANALYSIS
# =========================================================
with tab5:

    st.header("AMC Portfolio Overlap Analysis")

    months_sorted = sorted(
        change_df["Month"].unique(),
        key=lambda x: datetime.strptime(x, "%b%y"),
        reverse=True
    )
    if len(months_sorted) == 0:
        st.warning("No data available for selected filters")
        st.stop()

    latest_month = months_sorted[0]

    selected_month_4 = st.selectbox(
        "Select Month for Analysis",
        months_sorted,
        index=months_sorted.index(latest_month), key="4"
    )

    st.markdown("""
    <div style='width: fit-content; background-color:#F4F6F7; padding:12px 16px; border-radius:8px; margin-left:auto;'>
        <div style='text-align:center; font-weight:600; margin-bottom:6px;'>Ideal Overlap Range</div>
        <div style='text-align:center; font-size:14px; line-height:1.6'>
            0–20% → Good Diversification<br>
            20–50% → Moderate Overlap<br>
            50%+ → High Duplication Risk
        </div>
    </div>
    """, unsafe_allow_html=True)

    overlap_df = filtered_df[filtered_df["Month"] == selected_month_4]

    pivot_qty = (
        overlap_df.pivot_table(index="ISIN", columns="AMC", values="%_to_NAV", aggfunc="sum")
        .fillna(0)
    )

    amcs = pivot_qty.columns.tolist()
    overlap_matrix = pd.DataFrame(index=amcs, columns=amcs)

    for amc1 in amcs:
        for amc2 in amcs:
            q1 = pivot_qty[amc1]
            q2 = pivot_qty[amc2]
            min_sum = (pd.concat([q1, q2], axis=1).min(axis=1)).sum()
            max_sum = (pd.concat([q1, q2], axis=1).max(axis=1)).sum()
            overlap_pct = (min_sum / max_sum) * 100 if max_sum != 0 else 0
            overlap_matrix.loc[amc1, amc2] = round(overlap_pct, 2)

    overlap_matrix = overlap_matrix.astype(float)

    fig_overlap = px.imshow(
        overlap_matrix, text_auto=True, aspect="auto",
        color_continuous_scale="Reds", title="AMC Overlap (%)"
    )
    fig_overlap.update_layout(height=650, font=dict(size=14), title_font_size=22)
    st.plotly_chart(fig_overlap, width='stretch')

    st.subheader("Overlapping Stocks (Based on Quantity Presence)")

    overlap_counts = (pivot_qty > 0).sum(axis=1)
    overlap_isins = overlap_counts[overlap_counts >= 2].index
    overlap_stocks_df = overlap_df[overlap_df["ISIN"].isin(overlap_isins)]

    pivot_table = (
        overlap_stocks_df.pivot_table(
            index=["Share Name", "Industry"], columns="AMC",
            values="%_to_NAV", aggfunc="sum"
        )
        .fillna(0)
        .reset_index()
    )
    pivot_table = pivot_table.sort_values(by=list(pivot_table.columns[2:]), ascending=False)
    st.dataframe(pivot_table, width='stretch')
# =========================================================
# TAB X - INDUSTRY LEVEL MONTHLY CHANGE
# =========================================================
with tab7:

    st.header("Monthly Change in Industry Holding")

    # -------------------- MONTH SELECTION --------------------
    col1, col2 = st.columns(2)

    with col1:
        month_1_ind = st.selectbox(
            "Select Base Month",
            months_sorted,
            index=1 if len(months_sorted) > 1 else 0,
            key="month1_industry"
        )

    with col2:
        month_2_ind = st.selectbox(
            "Select Comparison Month",
            months_sorted,
            index=0,
            key="month2_industry"
        )

    # -------------------- PREPARE DATA --------------------
    df_m1_ind = filtered_df[
        filtered_df["Month"] == month_1_ind
    ]

    df_m2_ind = filtered_df[
        filtered_df["Month"] == month_2_ind
    ]

    # 🔥 GROUP AT AMC + INDUSTRY LEVEL
    df_m1_ind = (
        df_m1_ind.groupby(["AMC", "Industry"])["Quantity"]
        .sum()
        .reset_index()
    )

    df_m2_ind = (
        df_m2_ind.groupby(["AMC", "Industry"])["Quantity"]
        .sum()
        .reset_index()
    )

    merged_ind_df = pd.merge(
        df_m1_ind,
        df_m2_ind,
        on=["AMC", "Industry"],
        how="outer",
        suffixes=("_m1", "_m2")
    ).fillna(0)

    # -------------------- CHANGE CALCULATION --------------------
    merged_ind_df["Change"] = (
        merged_ind_df["Quantity_m2"] -
        merged_ind_df["Quantity_m1"]
    )

    merged_ind_df["Per_Change"] = merged_ind_df.apply(
        lambda row: (
            row["Change"] / row["Quantity_m1"] * 100
        ) if row["Quantity_m1"] != 0 else 0,
        axis=1
    )

    # -------------------- INCREASE --------------------
    st.subheader(f"Increase in Industry Holdings ({month_1_ind} → {month_2_ind})")

    top_n_inc_ind = st.slider(
        "Select Top N Industry Increases",
        5, 50, 20,
        key="inc_slider_industry"
    )

    increase_ind_df = merged_ind_df[
        merged_ind_df["Change"] > 0
    ].sort_values("Per_Change", ascending=False)

    fig_inc_ind = px.bar(
        increase_ind_df.head(top_n_inc_ind),
        x="Industry",
        y="Per_Change",
        color="AMC",
        text="Per_Change",
        color_discrete_map=amc_color_map,
        title="Top Increases in Industry Holdings (%)"
    )

    fig_inc_ind.update_traces(
        texttemplate='<b>%{text:.2f}%</b>',
        textposition="outside"
    )

    fig_inc_ind.update_layout(
        height=650,
        xaxis_tickangle=-45,
        font=dict(size=14)
    )

    st.plotly_chart(fig_inc_ind, width='stretch')

    # -------------------- DECREASE --------------------
    st.subheader(f"Decrease in Industry Holdings ({month_1_ind} → {month_2_ind})")

    top_n_dec_ind = st.slider(
        "Select Top N Industry Decreases",
        5, 50, 20,
        key="dec_slider_industry"
    )

    decrease_ind_df = merged_ind_df[
        merged_ind_df["Change"] < 0
    ].sort_values("Per_Change")

    fig_dec_ind = px.bar(
        decrease_ind_df.head(top_n_dec_ind),
        x="Industry",
        y="Per_Change",
        color="AMC",
        text="Per_Change",
        color_discrete_map=amc_color_map,
        title="Top Decreases in Industry Holdings (%)"
    )

    fig_dec_ind.update_traces(
        texttemplate='<b>%{text:.2f}%</b>',
        textposition="outside"
    )

    fig_dec_ind.update_layout(
        height=650,
        xaxis_tickangle=-45,
        font=dict(size=14)
    )

    st.plotly_chart(fig_dec_ind, width='stretch')

# =========================================================
# TAB 8 - STOCKS TO WATCH (CONSENSUS SIGNAL)
# =========================================================
with tab8:

    st.header("🚀 Stocks to Watch (Consensus Smart Money)")

    # -------------------- USER CONTROLS --------------------
    col1, col2 = st.columns(2)

    with col1:
        base_month = st.selectbox(
            "Base Month",
            months_sorted,
            index=1 if len(months_sorted) > 1 else 0,
            key="watch_base"
        )

    with col2:
        curr_month = st.selectbox(
            "Current Month",
            months_sorted,
            index=0,
            key="watch_curr"
        )

    min_amc = st.slider("Minimum AMCs Buying", 1, 5, 2)

    # -------------------- DATA PREP --------------------
    df_m1 = filtered_df[filtered_df["Month"] == base_month]
    df_m2 = filtered_df[filtered_df["Month"] == curr_month]

    df_m1 = df_m1.groupby(["AMC", "ISIN"])["Quantity"].sum().reset_index()
    df_m2 = df_m2.groupby(["AMC", "ISIN"])["Quantity"].sum().reset_index()

    merged = pd.merge(
        df_m1,
        df_m2,
        on=["AMC", "ISIN"],
        how="outer",
        suffixes=("_m1", "_m2")
    ).fillna(0)

    # -------------------- CALCULATIONS --------------------
    merged["Change"] = merged["Quantity_m2"] - merged["Quantity_m1"]

    merged["Per_Change"] = merged.apply(
        lambda row: (row["Change"] / row["Quantity_m1"] * 100)
        if row["Quantity_m1"] != 0 else 0,
        axis=1
    )

    # 🔥 KEY CHANGE: ONLY POSITIVE BUYING AMCs
    buying_df = merged[merged["Change"] > 0]

    # -------------------- STOCK LEVEL --------------------
    stock_level = buying_df.groupby("ISIN").agg({
        "Change": "sum",
        "Per_Change": "mean",
        "AMC": "nunique"
    }).rename(columns={
        "Change": "Total_Change",
        "Per_Change": "Avg_%_Change",
        "AMC": "Buying_AMC_Count"
    }).reset_index()

    # -------------------- NEW ENTRY --------------------
    new_entries = merged[
        (merged["Quantity_m1"] == 0) & (merged["Quantity_m2"] > 0)
    ]["ISIN"].unique()

    stock_level["New_Entry"] = stock_level["ISIN"].isin(new_entries)

    # -------------------- SCORING MODEL --------------------
    stock_level["Score"] = (
        (stock_level["Total_Change"].rank(pct=True) * 0.35) +
        (stock_level["Avg_%_Change"].rank(pct=True) * 0.25) +
        (stock_level["Buying_AMC_Count"].rank(pct=True) * 0.30) +
        (stock_level["New_Entry"].astype(int) * 0.10)
    )

    # -------------------- MERGE NAMES --------------------
    stock_level = stock_level.merge(master_isin, on="ISIN", how="left")

    # -------------------- FINAL FILTER --------------------
    final_df = stock_level[
        (stock_level["Total_Change"] > 0) &
        (stock_level["Buying_AMC_Count"] >= min_amc)
    ].sort_values("Score", ascending=False)

    # -------------------- OUTPUT --------------------
    top_n = st.slider("Top N Stocks", 5, 50, 15)

    st.dataframe(
        final_df.head(top_n)[[
            "Share Name",
            "Industry",
            "Score",
            "Buying_AMC_Count",
            "Total_Change",
            "Avg_%_Change",
            "New_Entry"
        ]],
        width='stretch'
    )

    # -------------------- VISUAL --------------------
    fig = px.bar(
        final_df.head(top_n),
        x="Share Name",
        y="Score",
        color="Industry",
        title="Top Consensus Buys"
    )

    fig.update_layout(height=600)

    st.plotly_chart(fig, width='stretch')
