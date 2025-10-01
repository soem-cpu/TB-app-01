import streamlit as st
import pandas as pd
import importlib.util
import io
from PIL import Image

# =========================
# 🔹 Page Config
# =========================
st.set_page_config(
    page_title="TB Data Verification",
    layout="wide",
    page_icon="📊"
)

# =========================
# 🔹 Sidebar with Logo / Image
# =========================
with st.sidebar:
    st.image("https://www.who.int/images/default-source/imported/tuberculosis.jpg", 
             caption="Stop TB Initiative", use_container_width=True)
    st.markdown("### 📌 Instructions")
    st.markdown("""
    1. Upload **Rules file (.py)**
    2. Upload **Excel/CSV data**
    3. Review validation results
    4. Download corrected file
    """)
    st.markdown("---")
    st.info("💡 Tip: Ensure your rules file and dataset follow the same column names.")

# =========================
# 🔹 Main Title & Description
# =========================
st.title("🩺 Tuberculosis Data Verification System")
st.markdown("""
This tool allows **rule-based validation** of TB datasets.  
Upload your **Python rules file** and your **Excel dataset** to generate a **multi-sheet Excel report** with identified issues.
""")

# =========================
# 🔹 Upload Rules File
# =========================
st.subheader("📥 Step 1: Upload Rules File")
rules_file = st.file_uploader("Upload your Python rules file (.py)", type=["py"])

if rules_file:
    with open("rules_temp.py", "wb") as f:
        f.write(rules_file.getbuffer())
    spec = importlib.util.spec_from_file_location("rules_module", "rules_temp.py")
    rules_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rules_module)
    st.success("✅ Rules file loaded successfully!")

# =========================
# 🔹 Upload Data File
# =========================
st.subheader("📥 Step 2: Upload Data File")
data_file = st.file_uploader("Upload Excel or CSV data", type=["xlsx", "csv"])

# =========================
# 🔹 Apply Rules if Both Files Uploaded
# =========================
if data_file and rules_file:
    st.subheader("👀 Step 3: Data Preview")

    if data_file.name.endswith("xlsx"):
        xls = pd.ExcelFile(data_file)
        preview_sheet = xls.sheet_names[0]
        df_preview = xls.parse(preview_sheet)
        st.info(f"Preview of uploaded data (first sheet: **{preview_sheet}**)")
        st.dataframe(df_preview.head())
    else:
        df_preview = pd.read_csv(data_file)
        st.info("Preview of uploaded CSV")
        st.dataframe(df_preview.head())

    # =========================
    # 🔹 Apply Rule Checks
    # =========================
    st.subheader("🔍 Step 4: Run Rule Checks")
    try:
        results = rules_module.check_rules(data_file)
        excel_output = io.BytesIO()
        sheet_count = 0

        with pd.ExcelWriter(excel_output, engine="xlsxwriter") as writer:
            if isinstance(results, dict):
                st.markdown("## 📑 Validation Results by Sheet")
                for k, v in results.items():
                    st.markdown(f"### 📂 {k}")
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

        # =========================
        # 🔹 Download Button
        # =========================
        if sheet_count > 0:
            st.download_button(
                label="⬇️ Download All Results (Excel)",
                data=excel_output.getvalue(),
                file_name="TB_Validation_Results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"❌ Error running rules: {e}")

# =========================
# 🔹 Footer
# =========================
st.markdown("---")
st.caption("🔬 Developed for TB Data Quality Assurance | Powered by Streamlit")
