import streamlit as st
import pandas as pd
import importlib.util
import io

st.set_page_config(page_title="Dynamic Rule-Based Data Verification", layout="wide")
st.title("📊 Dynamic Rule-Based Data Verification App")

st.markdown("""
Upload your **Python rules file** and the **Excel file** you want to verify.
The app will dynamically apply the rules and show validation tables.
You can download all results as a single Excel file with multiple sheets.
""")

# Upload rules file (.py)
rules_file = st.file_uploader("Upload your Python rules file (.py)", type=["py"])
if rules_file:
    with open("rules_temp.py", "wb") as f:
        f.write(rules_file.getbuffer())
    spec = importlib.util.spec_from_file_location("rules_module", "rules_temp.py")
    rules_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rules_module)
    st.success("✅ Rules file loaded!")

# Upload Excel data file
data_file = st.file_uploader("Upload Excel file to verify", type=["xlsx", "csv"])
if data_file and rules_file:
    # Preview logic
    if data_file.name.endswith("xlsx"):
        xls = pd.ExcelFile(data_file)
        preview_sheet = xls.sheet_names[0]
        df_preview = xls.parse(preview_sheet)
        st.write(f"Preview of uploaded data (first sheet: {preview_sheet}):")
        st.dataframe(df_preview.head())
    else:
        df_preview = pd.read_csv(data_file)
        st.write("Preview of uploaded data:")
        st.dataframe(df_preview.head())

    # Apply rules
try:
    results = rules_module.check_rules(data_file)
    excel_output = io.BytesIO()

    if isinstance(results, dict):
        # --- Summary ---
        st.markdown("## 📋 Summary of Findings")
        summary_data = []
        for sheet_name, df in results.items():
            if isinstance(df, pd.DataFrame):
                issues = df["Comment"].astype(str).ne("").sum() if "Comment" in df.columns else 0
                total_rows = len(df)
                summary_data.append({
                    "Sheet": sheet_name,
                    "Total Rows": total_rows,
                    "Findings": issues
                })
        if summary_data:
            st.dataframe(pd.DataFrame(summary_data))

        # --- Tabs for results ---
        tabs = st.tabs(list(results.keys()))
        with pd.ExcelWriter(excel_output, engine='xlsxwriter') as writer:
            for i, (sheet_name, df) in enumerate(results.items()):
                with tabs[i]:
                    st.markdown(f"### {sheet_name}")
                    if isinstance(df, pd.DataFrame):
                        if df.empty:
                            st.success("✅ No issues found!")
                        else:
                            st.dataframe(df)
                        df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
                    else:
                        st.write(df)

    elif isinstance(results, pd.DataFrame):
        st.markdown("## 📋 Summary of Findings")
        findings = results["Comment"].astype(str).ne("").sum() if "Comment" in results.columns else 0
        st.metric("Total Findings", findings)

        st.markdown("## Validation Results")
        if results.empty:
            st.success("✅ No validation issues found!")
        else:
            st.dataframe(results)

        with pd.ExcelWriter(excel_output, engine='xlsxwriter') as writer:
            results.to_excel(writer, index=False, sheet_name="Validation")

    # --- Download button ---
    st.download_button(
        label="📥 Download ALL Results as Excel (multi-sheet)",
        data=excel_output.getvalue(),
        file_name="all_results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

except Exception as e:
    st.error(f"❌ Error running rules: {e}")


st.markdown("---")
st.markdown("Created with Streamlit")
