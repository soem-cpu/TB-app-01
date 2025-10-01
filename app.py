import streamlit as st
import pandas as pd
import importlib.util
import io
from PIL import Image

# ------------------- Page Config -------------------
st.set_page_config(
    page_title="Dynamic Rule-Based Data Verification",
    layout="wide",
    page_icon="🩺"
)

# ------------------- Header -------------------
st.image("https://www.who.int/images/default-source/searo---images/tuberculosis/tb-microscope.tmb-1200v.jpg",
         caption="Tuberculosis Data Verification", use_container_width=True)

st.title("📊 Dynamic Rule-Based Data Verification App")
st.markdown("""
Upload your **Python rules file** and the **Excel/CSV data file** you want to verify.  
The app will apply rules dynamically and show validation tables.  
You can **download all results** as a single Excel file with multiple sheets.
""")

st.divider()

# ------------------- Upload Rules File -------------------
rules_file = st.file_uploader("📂 Upload your Python rules file (.py)", type=["py"])
if rules_file:
    with open("rules_temp.py", "wb") as f:
        f.write(rules_file.getbuffer())
    spec = importlib.util.spec_from_file_location("rules_module", "rules_temp.py")
    rules_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rules_module)
    st.success("✅ Rules file loaded!")

# ------------------- Upload Data File -------------------
data_file = st.file_uploader("📊 Upload Excel or CSV file to verify", type=["xlsx", "csv"])
if data_file and rules_file:
    try:
        # Preview logic
        if data_file.name.endswith("xlsx"):
            df_preview = pd.read_excel(data_file, engine="openpyxl")
            st.write("### 🔎 Data Preview (first 10 rows):")
            st.dataframe(df_preview.head(10), use_container_width=True)
        else:
            df_preview = pd.read_csv(data_file)
            st.write("### 🔎 Data Preview (first 10 rows):")
            st.dataframe(df_preview.head(10), use_container_width=True)

        # Apply rules
        results = rules_module.check_rules(data_file)
        excel_output = io.BytesIO()
        sheet_count = 0

        with pd.ExcelWriter(excel_output, engine="xlsxwriter") as writer:
            if isinstance(results, dict):
                st.markdown("## 📑 Validation Results:")
                for k, v in results.items():
                    st.subheader(f"📌 {k}")
                    if isinstance(v, pd.DataFrame):
                        if not v.empty:
                            st.dataframe(v, use_container_width=True)
                        else:
                            st.success(f"No issues found in **{k}** ✅")
                        v.to_excel(writer, index=False, sheet_name=k[:31])
                        sheet_count += 1
                    else:
                        st.write(v)
            elif isinstance(results, pd.DataFrame):
                if results.empty:
                    st.success("✅ No validation issues found!")
                else:
                    st.write("Validation results:")
                    st.dataframe(results, use_container_width=True)
                results.to_excel(writer, index=False, sheet_name="Validation")
                sheet_count += 1

        if sheet_count > 0:
            st.download_button(
                label="⬇️ Download ALL Results as Excel",
                data=excel_output.getvalue(),
                file_name="all_results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"❌ Error running rules: {e}")

st.divider()
st.markdown("🩺 Built with ❤️ using **Streamlit** for TB data verification.")
