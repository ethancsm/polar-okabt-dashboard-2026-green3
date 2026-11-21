import io
import os
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ─────────────────────────────────────────────
# 한글 폰트 (Streamlit CSS)
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap');
html, body, [class*="css"] {
   font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 데이터 로딩 (캐시)
# ─────────────────────────────────────────────
@st.cache_data
def load_env_data(file):
    if file is None:
        return pd.DataFrame()
    data = file.getvalue()
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(io.BytesIO(data), encoding=enc)
        except Exception:
            pass
    return pd.DataFrame()

@st.cache_data
def load_growth_data(file):
    if file is None:
        return pd.DataFrame()
    data = file.getvalue()
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(io.BytesIO(data), encoding=enc)
        except Exception:
            pass
    return pd.DataFrame()

# ─────────────────────────────────────────────
# 열 이름 표준화
# ─────────────────────────────────────────────
def std_cols(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    rename = {}
    for c in df.columns:
        k = c.lower().replace(" ", "")
        if k in ("time", "categories", "시간", "날짜", "datetime", "date"):
            rename[c] = "time"
        elif k in ("temperature", "온도"):
            rename[c] = "temperature"
        elif k in ("humidity", "습도"):
            rename[c] = "humidity"
        elif k == "ph":
            rename[c] = "ph"
        elif k == "ec":
            rename[c] = "ec"
        elif "생중량" in k:
            rename[c] = "생중량"
        elif "잎" in k:
            rename[c] = "잎 수"
        elif "지상부" in k and "길이" in k:
            rename[c] = "지상부 길이"
        elif "지하부" in k and "길이" in k:
            rename[c] = "지하부 길이"
        elif "지상부" in k and ("질량" in k or "무게" in k):
            rename[c] = "지상부 질량"
        elif "지하부" in k and ("질량" in k or "무게" in k):
            rename[c] = "지하부 질량"
        elif "개체" in k:
            rename[c] = "개체번호"
    df = df.rename(columns=rename)
    for c in df.columns:
        if c in ("time", "개체번호"):
            continue
        if not pd.api.types.is_numeric_dtype(df[c]):
            num = pd.to_numeric(
                df[c].astype(str).str.replace(",", "").
                str.extract(r"(-?\d+\.?\d*)")[0], errors="coerce"
            )
            if num.notna().mean() >= 0.5:
                df[c] = num
    if "생중량" not in df.columns and {"지상부 질량", "지하부 질량"} <= set(df.columns):
        df["생중량"] = df["지상부 질량"] + df["지하부 질량"]
    if "time" in df.columns:
        t = df["time"].astype(str).str.strip()
        parsed = pd.to_datetime(t, errors="coerce", format="mixed")
        bad = parsed.isna() & t.str.match(r"^\d{8}_\d{1,2}$")
        if bad.any():
            parts = t[bad].str.split("_", expand=True)
            parsed[bad] = pd.to_datetime(parts[0], format="%Y%m%d") + \
                          pd.to_timedelta(parts[1].astype(int), unit="h")
        df["time"] = parsed
    return df

# ─────────────────────────────────────────────
# 학교명 추출 (파일명에서)
# ─────────────────────────────────────────────
def get_school_name(filename):
    if filename is None:
        return "우리 학교"
    base = os.path.basename(filename)
    name = base.split("_")[0].strip()
    return name if name else "우리 학교"

# ─────────────────────────────────────────────
# 사이드바 구성
# ─────────────────────────────────────────────
st.set_page_config(page_title="극지식물 생육 대시보드", layout="wide")
st.title("극지식물 개체별 생육 차이 분석 대시보드")

with st.sidebar:
    st.header("CSV 업로드")
    env_file = st.file_uploader("환경 데이터 CSV", type="csv",
                                 help="time, temperature, humidity 등이 포함된 환경 측정 데이터")
    growth_file = st.file_uploader("생육 결과 CSV", type="csv",
                                    help="개체번호, 잎 수, 길이, 질량 등이 포함된 생육 측정 데이터")
    st.divider()
    growth_items = st.multiselect(
        "생육 측정 항목 (그래프에 포함할 항목)",
        ["잎 수", "지상부 길이", "지하부 길이", "생중량", "지상부 질량", "지하부 질량"],
        default=["잎 수", "지상부 길이", "생중량"],
        help="비교·분석할 생육 항목을 선택하세요.",
    )

school_name = get_school_name(
    growth_file.name if growth_file else (env_file.name if env_file else None)
)

# 데이터 읽기
with st.spinner("데이터를 읽고 표준화 중입니다..."):
    raw_env = load_env_data(env_file)
    raw_growth = load_growth_data(growth_file)
    env_df = std_cols(raw_env) if not raw_env.empty else pd.DataFrame()
    growth_df = std_cols(raw_growth) if not raw_growth.empty else pd.DataFrame()

st.sidebar.divider()
st.sidebar.info(
    f"학교명: **{school_name}**  |  환경 데이터 {len(env_df)}행 · 생육 데이터 {len(growth_df)}행"
)

# ─────────────────────────────────────────────
# 탭 구성
# ─────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "개체별 생육 현황",
    "생육 vs 환경 상관분석",
    "생육 지표 요약 & 다운로드",
])

# ─────────────────────────────────────────────
# 탭 1: 개체별 생육 현황
# ─────────────────────────────────────────────
with tab1:
    try:
        if growth_df.empty:
            st.info(
                "생육 결과 CSV를 사이드바에 업로드해주세요. "
                "개체별 생육 현황이 이곳에 표시됩니다."
            )
        else:
            if "개체번호" not in growth_df.columns:
                st.info(
                    "개체번호 열을 찾을 수 없어요. "
                    "개체번호가 있는 생육 CSV를 업로드해주세요."
                )
            else:
                agg_cols = [
                    c for c in ["잎 수", "지상부 길이", "지하부 길이",
                                "생중량", "지상부 질량", "지하부 질량"]
                    if c in growth_df.columns
                ]
                if not agg_cols:
                    st.info(
                        "생육 측정 항목 열(잎 수, 길이, 질량 등)이 "
                        "하나도 없어서 표시할 수 없어요."
                    )
                else:
                    indiv = growth_df.groupby("개체번호")[agg_cols].mean().reset_index()

                    st.subheader(f"{school_name} 극지식물 개체별 생육 현황")
                    st.caption(
                        "각 개체의 평균 생육 지표를 막대그래프로 비교합니다. "
                        "(평균: 여러 값을 더해 개수로 나눈 대표값 / "
                        "표준편차: 값들이 평균에서 얼마나 퍼져 있는지 나타내는 수치)"
                    )

                    available = [c for c in growth_items if c in indiv.columns]
                    if not available:
                        st.info(
                            "선택한 생육 항목이 데이터에 없어요. "
                            "다른 항목을 선택해보세요."
                        )
                    else:
                        data_sorted_all = {}
                        for col in available:
                            data_sorted_all[col] = indiv.sort_values(col, ascending=True)

                        fig = make_subplots(
                            rows=len(available), cols=1,
                            subplot_titles=[f"평균 {c}" for c in available],
                            vertical_spacing=0.12,
                        )
                        for i, col in enumerate(available):
                            ds = data_sorted_all[col]
                            colors = [
                                "#d62728" if v == ds[col].max()
                                else "#1f77b4" if v == ds[col].min()
                                else "#7ec8e3"
                                for v in ds[col]
                            ]
                            fig.add_trace(
                                go.Bar(
                                    x=ds["개체번호"].astype(str),
                                    y=ds[col],
                                    name=col,
                                    marker_color=colors,
                                    text=ds[col].round(2),
                                    textposition="outside",
                                ),
                                row=i + 1, col=1,
                            )
                            fig.update_xaxes(
                                title_text="개체번호", row=i + 1, col=1, tickangle=45
                            )
                            fig.update_yaxes(title_text=col, row=i + 1, col=1)
                        fig.update_layout(
                            height=200 * len(available) + 80,
                            font=dict(
                                family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"
                            ),
                            showlegend=False,
                            margin=dict(l=40, r=20, t=60, b=60),
                        )
                        st.plotly_chart(fig, width="stretch")

                    # 개체별 요약표
                    st.subheader("개체별 생육 지표 요약")
                    st.caption(
                        "- 평균(mean): 여러 값을 더해 개수로 나눈 대표값\n"
                        "- 표준편차(std): 값들이 평균에서 얼마나 퍼져 있는지\n"
                        "  (클수록 개체 간 차이가 큼)\n"
                        "- 최대/최소: 가장 큰 값 / 가장 작은 값"
                    )
                    summary = indiv[agg_cols].agg(["mean", "std", "min", "max"]).T
                    summary.columns = ["평균", "표준편차", "최소", "최대"]
                    summary = summary.round(2)
                    st.dataframe(summary, width="stretch")

                    # 생중량 상위·하위 개체 강조
                    if "생중량" in indiv.columns:
                        top5 = indiv.nlargest(5, "생중량")
                        bot5 = indiv.nsmallest(5, "생중량")
                        c1, c2 = st.columns(2)
                        with c1:
                            st.metric(
                                "생중량 최대 개체",
                                f"개체 {int(top5.iloc[0]['개체번호'])}",
                                f"{top5.iloc[0]['생중량']:.2f}g",
                            )
                            st.info(
                                "상위 5개체: "
                                + ", ".join([str(int(x)) for x in top5["개체번호"]])
                                + f"  |  평균 {top5['생중량'].mean():.2f}g"
                            )
                        with c2:
                            st.metric(
                                "생중량 최소 개체",
                                f"개체 {int(bot5.iloc[0]['개체번호'])}",
                                f"{bot5.iloc[0]['생중량']:.2f}g",
                            )
                            st.info(
                                "하위 5개체: "
                                + ", ".join([str(int(x)) for x in bot5["개체번호"]])
                                + f"  |  평균 {bot5['생중량'].mean():.2f}g"
                            )
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")

# ─────────────────────────────────────────────
# 탭 2: 생육 vs 환경 상관분석
# ─────────────────────────────────────────────
with tab2:
    try:
        if env_df.empty and growth_df.empty:
            st.info(
                "환경 데이터와 생육 결과 CSV를 모두 사이드바에 업로드해주세요. "
                "상관분석 결과가 이곳에 표시됩니다."
            )
        elif env_df.empty:
            st.info(
                "환경 데이터 CSV를 사이드바에 업로드해주세요. "
                "생육 데이터와 함께 분석하면 상관 그래프를 볼 수 있어요."
            )
        elif growth_df.empty:
            st.info(
                "생육 결과 CSV를 사이드바에 업로드해주세요. "
                "환경 데이터와 함께 분석하면 상관 그래프를 볼 수 있어요."
            )
        else:
            if "time" not in env_df.columns:
                st.info(
                    "환경 데이터에 time 열이 없어서 "
                    "시간 기반 상관분석을 할 수 없어요."
                )
            else:
                env_t = env_df.dropna(subset=["time"])
                if env_t.empty:
                    st.info(
                        "환경 데이터의 시간 값이 모두 비어 있어서 분석할 수 없어요."
                    )
                else:
                    env_cols = [
                        c for c in ["temperature", "humidity", "ph", "ec",
                                    "water_temp", "co2"]
                        if c in env_df.columns
                    ]
                    gr_cols = [
                        c for c in ["잎 수", "지상부 길이", "지하부 길이",
                                    "생중량", "지상부 질량", "지하부 질량"]
                        if c in growth_df.columns and c in growth_items
                    ]

                    if not env_cols:
                        st.info(
                            "환경 데이터에서 온도, 습도, pH, EC 등 "
                            "수치 열을 하나도 찾을 수 없어요."
                        )
                    elif not gr_cols:
                        st.info(
                            "선택한 생육 측정 항목이 생육 데이터에 없어서 "
                            "상관분석을 할 수 없어요. "
                            "사이드바에서 항목을 선택해보세요."
                        )
                    else:
                        # 일별 평균으로 병합
                        env_daily = (
                            env_t.set_index("time")
                            .groupby(pd.Grouper(freq="D"))[env_cols]
                            .mean()
                        )
                        if "time" in growth_df.columns:
                            gr_t = growth_df.dropna(subset=["time"])
                            gr_daily = (
                                gr_t.set_index("time")
                                .groupby(pd.Grouper(freq="D"))[gr_cols]
                                .mean()
                            )
                        else:
                            gr_daily = (
                                growth_df[gr_cols].mean().to_frame().T
                            )

                        merged = env_daily.join(gr_daily, how="inner").dropna()

                        if len(merged) < 2:
                            st.info(
                                "환경 데이터와 생육 데이터의 공통 기간이 너무 짧아 "
                                "(상관계 계산에 필요한 2개 이상 데이터 포인트가 없음) "
                                "상관분석을 할 수 없어요."
                            )
                        else:
                            st.subheader(
                                f"{school_name} 환경 요인 vs 생육 지표 상관분석"
                            )
                            st.caption(
                                "- 상관계수(correlation coefficient): -1 ~ +1 사이 값\n"
                                "  +1에 가까울수록 함께 증가, -1에 가까울수록 반대로 움직임\n"
                                "  0에 가까우면 관계가 약함\n"
                                "- 추세선(빨간 점선): np.polyfit으로 구한 직선"
                            )

                            avail_gr = [c for c in gr_cols if c in merged.columns]
                            for ecol in env_cols:
                                if not avail_gr:
                                    continue
                                fig = make_subplots(
                                    rows=len(avail_gr), cols=1,
                                    subplot_titles=[
                                        f"{ecol} vs {gcol}" for gcol in avail_gr
                                    ],
                                    vertical_spacing=0.12,
                                )
                                for i, gcol in enumerate(avail_gr):
                                    sub = merged[[ecol, gcol]].dropna()
                                    if len(sub) < 2:
                                        fig.add_trace(
                                            go.Scatter(
                                                x=[], y=[], mode="markers",
                                                name="데이터 부족"
                                            ),
                                            row=i + 1, col=1,
                                        )
                                        continue
                                    x = sub[ecol].values
                                    y = sub[gcol].values
                                    r = np.corrcoef(x, y)[0, 1]
                                    slope, intercept = np.polyfit(x, y, 1)
                                    x_line = np.linspace(x.min(), x.max(), 100)
                                    y_line = slope * x_line + intercept
                                    fig.add_trace(
                                        go.Scatter(
                                            x=x, y=y, mode="markers",
                                            name=f"r = {r:.2f}",
                                            marker=dict(color="#1f77b4"),
                                        ),
                                        row=i + 1, col=1,
                                    )
                                    fig.add_trace(
                                        go.Scatter(
                                            x=x_line, y=y_line, mode="lines",
                                            line=dict(
                                                color="#d62728", dash="dash",
                                                width=2
                                            ),
                                            name="추세선",
                                        ),
                                        row=i + 1, col=1,
                                    )
                                    fig.update_xaxes(
                                        title_text=ecol, row=i + 1, col=1
                                    )
                                    fig.update_yaxes(
                                        title_text=gcol, row=i + 1, col=1
                                    )
                                fig.update_layout(
                                    height=200 * len(avail_gr) + 60,
                                    font=dict(
                                        family="Malgun Gothic, "
                                        "Apple SD Gothic Neo, sans-serif"
                                    ),
                                    showlegend=True,
                                    margin=dict(l=40, r=20, t=60, b=60),
                                )
                                st.plotly_chart(fig, width="stretch")

                            # 상관계수 요약 표
                            st.subheader("상관계수 요약 표")
                            corr_rows = []
                            for ecol in env_cols:
                                for gcol in gr_cols:
                                    if gcol in merged.columns:
                                        sub = merged[[ecol, gcol]].dropna()
                                        if len(sub) >= 2:
                                            r = np.corrcoef(sub[ecol], sub[gcol])[0, 1]
                                            corr_rows.append({
                                                "환경 요인": ecol,
                                                "생육 지표": gcol,
                                                "상관계수(r)": round(r, 3),
                                            })
                            if corr_rows:
                                corr_df = pd.DataFrame(corr_rows)
                                st.dataframe(corr_df, width="stretch")
                            else:
                                st.info(
                                    "상관계수를 계산할 공통 데이터가 부족해요."
                                )
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")

# ─────────────────────────────────────────────
# 탭 3: 생육 지표 요약 & 다운로드
# ─────────────────────────────────────────────
with tab3:
    try:
        if growth_df.empty:
            st.info(
                "생육 결과 CSV를 사이드바에 업로드해주세요. "
                "생육 지표 요약과 데이터 다운로드 버튼이 이곳에 표시됩니다."
            )
        else:
            gr_cols_all = [
                c for c in ["잎 수", "지상부 길이", "지하부 길이",
                            "생중량", "지상부 질량", "지하부 질량"]
                if c in growth_df.columns
            ]
            if not gr_cols_all:
                st.info(
                    "생육 데이터에 수치 열(잎 수, 길이, 질량 등)이 "
                    "하나도 없어서 요약할 수 없어요."
                )
            else:
                st.subheader(f"{school_name} 생육 지표 요약")
                st.caption(
                    "아래 표는 모든 개체의 생육 지표에 대한 기본 통계예요.\n"
                    "- 평균(mean): 여러 값의 중심 representative value\n"
                    "- 표준편차(std): 평균에서 얼마나 퍼져 있는지\n"
                    "- 비대칭도(skewness): 분포가 한쪽으로 치우친 정도\n"
                    "  (0이면 대칭, 양수면 오른쪽 꼬리가 긺, 음수면 왼쪽 꼬리가 긺)"
                )

                stats_rows = []
                for col in gr_cols_all:
                    vals = growth_df[col].dropna()
                    if len(vals) == 0:
                        continue
                    stats_rows.append({
                        "측정 항목": col,
                        "개체 수": len(vals),
                        "평균": round(vals.mean(), 2),
                        "표준편차": round(vals.std(), 2),
                        "최소": round(vals.min(), 2),
                        "최대": round(vals.max(), 2),
                        "비대칭도": round(vals.skew(), 3),
                    })
                if stats_rows:
                    stats_df = pd.DataFrame(stats_rows)
                    st.dataframe(stats_df, width="stretch")

                # 분포 히스토그램
                st.subheader("개체별 생육 지표 분포")
                avail_hist = [c for c in growth_items if c in growth_df.columns]
                if avail_hist:
                    n_hist = min(len(avail_hist), 6)
                    colors_hist = [
                        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
                        "#9467bd", "#8c564b",
                    ]
                    fig = make_subplots(
                        rows=n_hist, cols=1,
                        subplot_titles=avail_hist[:n_hist],
                        vertical_spacing=0.12,
                    )
                    for i, col in enumerate(avail_hist[:n_hist]):
                        data = growth_df[col].dropna()
                        if len(data) == 0:
                            continue
                        fig.add_trace(
                            go.Histogram(
                                x=data, nbinsx=20, name=col,
                                marker_color=colors_hist[i % len(colors_hist)],
                                opacity=0.7,
                            ),
                            row=i + 1, col=1,
                        )
                        fig.update_xaxes(title_text=col, row=i + 1, col=1)
                        fig.update_yaxes(title_text="개체 수", row=i + 1, col=1)
                    fig.update_layout(
                        height=180 * n_hist + 60,
                        font=dict(
                            family="Malgun Gothic, "
                            "Apple SD Gothic Neo, sans-serif"
                        ),
                        showlegend=False,
                        margin=dict(l=40, r=20, t=60, b=60),
                    )
                    st.plotly_chart(fig, width="stretch")
                else:
                    st.info("사이드바에서 생육 측정 항목을 선택해주세요.")

                # 다운로드 버튼
                st.divider()
                st.subheader("데이터 다운로드")
                st.caption(
                    "환경 데이터와 생육 결과 데이터를 각각 CSV로 다운로드할 수 있어요. "
                    "(한글 깨짐 방지를 위해 utf-8-sig 인코딩 사용)"
                )

                c1, c2 = st.columns(2)
                with c1:
                    if not env_df.empty:
                        env_csv = env_df.to_csv(index=False).encode("utf-8-sig")
                        st.download_button(
                            label="환경 데이터 다운로드 (CSV)",
                            data=env_csv,
                            file_name=f"{school_name}_환경데이터.csv",
                            mime="text/csv",
                        )
                    else:
                        st.info("환경 데이터가 업로드되지 않았어요.")
                with c2:
                    if not growth_df.empty:
                        gr_csv = growth_df.to_csv(index=False).encode("utf-8-sig")
                        st.download_button(
                            label="생육 결과 데이터 다운로드 (CSV)",
                            data=gr_csv,
                            file_name=f"{school_name}_생육결과데이터.csv",
                            mime="text/csv",
                        )
                    else:
                        st.info("생육 데이터가 업로드되지 않았어요.")
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")
