import streamlit as st
import pandas as pd
import importlib.util
import io
import tempfile
import os
import traceback

st.set_page_config(page_title="Dynamic Rule-Based Data Verification", layout="wide")
st.title("📊 Dynamic Rule-Based Data Verification App")

st.markdown(
    """
Upload your **Python rules file** and the **Excel/CSV file** you want to verify.
The app dynamically loads the rules file and runs `check_rules(...)`.  
You will see a summary of findings, per-sheet tabs, and a downloadable multi-sheet Excel.
"""
)

# -------------------- Upload rules file (.py) --------------------
rules_file = st.file_uploader("Upload your Python rules file (.py)", type=["py"])

rules_module = None
rules_temp_path = None
if rules_file:
    # write to a temporary file then import
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".py")
    try:
        tmp.write(rules_file.getbuffer())
        tmp.flush()
        tmp.close()
        rules_temp_path = tmp.name

        # load module from the temp file
        spec = importlib.util.spec_from_file_location("rules_module", rules_temp_path)
        rules_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rules_module)
        st.success("✅ Rules file loaded!")
    except Exception as e:
        st.error(f"Failed to load rules file: {e}")
        st.code(traceback.format_exc())
        # cleanup
        try:
            os.unlink(rules_temp_path)
        except Exception:
            pass
        rules_module = None

# -------------------- Upload data file --------------------
data_file = st.file_uploader("Upload Excel (.xlsx) or CSV (.csv) to verify", type=["xlsx", "csv"])

# small helper for counting findings (works even when Comment missing)
def count_findings_in_df(df):
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return 0
    # prefer Comment column if it exists
    if "Comment" in df.columns:
        return df["Comment"].astype(str).str.strip().ne("").sum()
    # fallback: any column that looks like error/duplicate/_check
    error_cols = [c for c in df.columns if ("Error" in c or "Duplicate" in c or c.lower().endswith("_check"))]
    if not error_cols:
        return 0
    mask = df[error_cols].astype(str).apply(lambda col: col.str.strip() != "")
    return (mask.any(axis=1)).sum()

# -------------------- Run rules and display results --------------------
if data_file and rules_module:
    # Preview
    st.markdown("### Preview of uploaded data")
    try:
        if getattr(data_file, "name", "").lower().endswith(".xlsx"):
            xls = pd.ExcelFile(data_file)
            preview_sheet = xls.sheet_names[0]
            df_preview = xls.parse(preview_sheet)
            st.write(f"First sheet: **{preview_sheet}**")
            st.dataframe(df_preview.head())
        else:
            df_preview = pd.read_csv(data_file)
            st.dataframe(df_preview.head())
    except Exception as e:
        st.error(f"Could not preview data file: {e}")
        st.code(traceback.format_exc())

    # Validate presence of check_rules
    if not hasattr(rules_module, "check_rules") or not callable(rules_module.check_rules):
        st.error("The uploaded rules file does not expose a callable `check_rules(excel_file)` function.")
    else:
        run_button = st.button("Run validation")
        if run_button:
            try:
                with st.spinner("Running rules..."):
                    # call user's check_rules - pass the uploaded file-like object
                    results = rules_module.check_rules(data_file)
            except Exception as e:
                st.error(f"❌ Error running rules: {e}")
                st.code(traceback.format_exc())
                results = None

            if results is None:
                st.warning("No results returned.")
            else:
                # Normalize results into dict of DataFrames
                if isinstance(results, pd.DataFrame):
                    results = {"Validation": results}
                elif not isinstance(results, dict):
                    st.write("Results (not a DataFrame/dict):")
                    st.write(results)
                    results = None

                if results:
                    # Build summary
                    summary_rows = []
                    for sheet_name, df in results.items():
                        if isinstance(df, pd.DataFrame):
                            total_rows = len(df)
                            findings = count_findings_in_df(df)
                        else:
                            total_rows = 0
                            findings = 0
                        summary_rows.append({"Sheet": sheet_name, "Total Rows": total_rows, "Findings": findings})

                    st.markdown("## 📋 Summary of Findings")
                    summary_df = pd.DataFrame(summary_rows).sort_values(by="Findings", ascending=False).reset_index(drop=True)
                    st.dataframe(summary_df)

                    # show metrics for top-level totals
                    total_findings = summary_df["Findings"].sum()
                    total_rows = summary_df["Total Rows"].sum()
                    cols = st.columns(3)
                    cols[0].metric("Sheets", len(summary_df))
                    cols[1].metric("Total rows (all sheets)", int(total_rows))
                    cols[2].metric("Total findings (all sheets)", int(total_findings))

                    # Tabs for each sheet
                    st.markdown("---")
                    st.markdown("## 🔎 Detailed Results (per sheet)")
                    sheet_names = list(results.keys())
                    tabs = st.tabs(sheet_names)
                    for i, sheet_name in enumerate(sheet_names):
                        with tabs[i]:
                            df = results[sheet_name]
                            if isinstance(df, pd.DataFrame):
                                st.markdown(f"### {sheet_name}")
                                r_cols = st.columns([1, 1, 3])
                                r_cols[0].write(f"Rows: **{len(df)}**")
                                r_cols[1].write(f"Findings: **{count_findings_in_df(df)}**")
                                show_only = r_cols[2].checkbox("Show only rows with findings", key=f"only_{sheet_name}")

                                # If user asked to show only findings, filter
                                display_df = df
                                if show_only:
                                    if "Comment" in df.columns:
                                        display_df = df[df["Comment"].astype(str).str.strip() != ""].copy()
                                    else:
                                        error_cols = [c for c in df.columns if ("Error" in c or "Duplicate" in c or c.lower().endswith("_check"))]
                                        if error_cols:
                                            mask = df[error_cols].astype(str).apply(lambda col: col.str.strip() != "")
                                            display_df = df[mask.any(axis=1)].copy()
                                        else:
                                            display_df = df.iloc[0:0]  # empty

                                if display_df.empty:
                                    st.success("✅ No items to show (no findings).")
                                else:
                                    # use an expander for big tables
                                    with st.expander(f"Show table ({len(display_df)} rows)"):
                                        st.dataframe(display_df)

                            else:
                                st.write(f"Sheet '{sheet_name}' is not a DataFrame:")
                                st.write(df)

                    # Prepare download: multi-sheet excel
                    excel_output = io.BytesIO()
                    try:
                        with pd.ExcelWriter(excel_output, engine="xlsxwriter") as writer:
                            for sheet_name, df in results.items():
                                if isinstance(df, pd.DataFrame):
                                    # Excel sheet names max 31 chars
                                    safe_name = sheet_name[:31]
                                    df.to_excel(writer, index=False, sheet_name=safe_name)
                                else:
                                    # put textual representation into a sheet
                                    tmp_df = pd.DataFrame({"Value": [str(df)]})
                                    tmp_df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
                            writer.save()
                        st.download_button(
                            label="📥 Download ALL Results as Excel (multi-sheet)",
                            data=excel_output.getvalue(),
                            file_name="all_results.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    except Exception as e:
                        st.error(f"Failed to prepare download file: {e}")
                        st.code(traceback.format_exc())

# footer
st.markdown("---")
st.markdown("Created with Streamlit")
