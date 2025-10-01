# app.py
import streamlit as st
import pandas as pd
import importlib.util
import tempfile
import os
import io
import traceback

st.set_page_config(page_title="Dynamic Rule-Based Data Verification", layout="wide")
st.title("📊 Dynamic Rule-Based Data Verification (Step 1)")

st.markdown(
    """
This app loads a **rules .py** file (must provide `check_rules(excel_file)`), and an **Excel/CSV** file to validate.
Step 1: load rules, preview data, run validation, show a compact summary of findings.
After you confirm this works we will add tabs, row highlighting, charts and downloads.
"""
)

# --------------------- Helpers ---------------------
def safe_import_pyfile(uploaded_file) -> tuple:
    """
    Save uploaded .py to a temp file and import it as a module.
    Returns (module, temp_path) or (None, None) on failure.
    """
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".py")
        tmp.write(uploaded_file.getbuffer())
        tmp.flush()
        tmp.close()
        spec = importlib.util.spec_from_file_location("rules_module", tmp.name)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, tmp.name
    except Exception as e:
        # cleanup
        try:
            tmp_name = tmp.name
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except Exception:
            pass
        raise

def count_findings_in_df(df: pd.DataFrame) -> int:
    """Count rows that contain any non-empty 'Comment' (preferred) or any Error/Check columns."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return 0
    if "Comment" in df.columns:
        return df["Comment"].astype(str).str.strip().ne("").sum()
    # fallback to _Error / Duplicate / _check
    cand = [c for c in df.columns if ("Error" in c or "Duplicate" in c or c.lower().endswith("_check"))]
    if not cand:
        return 0
    mask = df[cand].astype(str).apply(lambda col: col.str.strip() != "")
    return mask.any(axis=1).sum()

# --------------------- Upload rules ---------------------
st.header("1) Upload rules (.py)")
rules_file = st.file_uploader("Upload your Python rules file (must define check_rules)", type=["py"], key="rules_uploader")

if rules_file:
    try:
        module, module_path = safe_import_pyfile(rules_file)
        st.session_state["rules_module"] = module
        st.session_state["rules_module_path"] = module_path
        st.success("✅ Rules file loaded and module imported.")
        # show a short info about check_rules presence
        if hasattr(module, "check_rules") and callable(module.check_rules):
            st.info("Module exposes `check_rules(...)` — ready to run.")
        else:
            st.warning("Module loaded but `check_rules` function not found. The rules file must expose a callable `check_rules(excel_file)`.")
    except Exception as e:
        st.error("Failed to load rules file. See details below.")
        st.code(traceback.format_exc())
        st.session_state.pop("rules_module", None)
        st.session_state.pop("rules_module_path", None)

# --------------------- Upload data ---------------------
st.header("2) Upload data (.xlsx or .csv)")
data_file = st.file_uploader("Upload Excel (.xlsx) or CSV (.csv) to validate", type=["xlsx", "csv"], key="data_uploader")

df_preview = None
if data_file:
    try:
        if data_file.name.lower().endswith(".xlsx"):
            xls = pd.ExcelFile(data_file)
            first_sheet = xls.sheet_names[0]
            df_preview = xls.parse(first_sheet)
            st.write(f"Preview of first sheet: **{first_sheet}**")
            st.dataframe(df_preview.head(10))
        else:
            df_preview = pd.read_csv(data_file)
            st.write("Preview (CSV):")
            st.dataframe(df_preview.head(10))
    except Exception as e:
        st.error(f"Could not read data file: {e}")
        st.code(traceback.format_exc())

# --------------------- Run validation ---------------------
st.header("3) Run validation")
run_col1, run_col2 = st.columns([1,3])
run_button = run_col1.button("▶️ Run validation", disabled=("rules_module" not in st.session_state or data_file is None))

if run_button:
    if "rules_module" not in st.session_state:
        st.error("No rules module loaded. Please upload a rules .py file first.")
    elif data_file is None:
        st.error("No data file uploaded. Please upload Excel or CSV file to validate.")
    else:
        # Run check_rules and show summary
        try:
            with st.spinner("Running check_rules..."):
                # pass the uploaded file object directly (most of your functions use pd.ExcelFile which accepts file-like)
                results = st.session_state["rules_module"].check_rules(data_file)
        except Exception as e:
            st.error("Error while running rules. See traceback for details.")
            st.code(traceback.format_exc())
            results = None

        if results is not None:
            # normalize results to dict of DataFrames
            if isinstance(results, pd.DataFrame):
                results = {"Validation": results}
            elif not isinstance(results, dict):
                st.warning("Rules returned a non-dict/non-DataFrame result — displaying raw output.")
                st.write(results)
                results = None

            if results:
                # Build and show summary table quickly
                summary = []
                for sheet_name, df in results.items():
                    if isinstance(df, pd.DataFrame):
                        total = len(df)
                        found = count_findings_in_df(df)
                    else:
                        total = 0
                        found = 0
                    summary.append({"Sheet": sheet_name, "Total Rows": total, "Findings": found})
                summary_df = pd.DataFrame(summary).sort_values("Findings", ascending=False).reset_index(drop=True)
                st.markdown("### 📋 Summary of Findings")
                st.dataframe(summary_df)

                # Show small per-sheet previews (first 10 rows); we will expand later with tabs
                st.markdown("### 🔎 Per-sheet preview")
                for sheet_name, df in results.items():
                    st.subheader(sheet_name)
                    if isinstance(df, pd.DataFrame):
                        if df.empty:
                            st.success("No issues found in this sheet!")
                        else:
                            # show up to first 10 rows (optionally filtered later)
                            with st.expander(f"Show up to 200 rows of {sheet_name} (first 10 shown)"):
                                st.dataframe(df.head(200))
                    else:
                        st.write(df)

                # store results in session_state for next steps (tabs, downloads in future)
                st.session_state["last_results"] = results
                st.success("Validation finished and results stored in session state.")

# footer
st.markdown("---")
st.markdown("Next: after you confirm this works, I'll add: tabs, highlighted rows, downloadable multi-sheet Excel, and charts.")
