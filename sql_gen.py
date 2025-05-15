import os
import time
import streamlit as st
from dotenv import load_dotenv
import pandas as pd
import sqlite3
from sqlalchemy import create_engine
from langchain_groq import ChatGroq

# Load environment variables
load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    st.error("GROQ_API_KEY not found in .env file.")
    st.stop()

# Initialize ChatGroq
llm = ChatGroq(model="llama-3.1-8b-instant", groq_api_key=groq_api_key, temperature=0.7, max_tokens=500)

# Initialize SQLite database
db_path = "database.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Initialize session state for chat history and sheets
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "sheets" not in st.session_state:
    st.session_state.sheets = {}

st.image("imagebanner1.png", use_column_width=True)

# Function to load and read multiple Excel files
def load_excel_files(uploaded_files):
    all_sheets = {}
    for uploaded_file in uploaded_files:
        xls = pd.ExcelFile(uploaded_file)
        for sheet_name in xls.sheet_names:
            all_sheets[sheet_name] = pd.read_excel(xls, sheet_name)
    return all_sheets

# Function to analyze data and provide recommendations
def analyze_data(sheets):
    response = ""
    for sheet_name, df in sheets.items():
        response += f"Table '{sheet_name}' has {df.shape[0]} rows and {df.shape[1]} columns.\n\n"
        if df.isnull().values.any():
            response += f"Warning: The sheet '{sheet_name}' contains missing values. This might affect SQL generation.\n"
        prompt = f"Explain the contents of the following table:\n{df.head().to_string()}"
        explanation = chat_with_assistant(prompt, "You are a helpful assistant, SQL programmer, data scientist, and generative AI specialist.")
        response += f"Explanation: {explanation}\n\n"
    return response

# Chat with the assistant using ChatGroq
def chat_with_assistant(prompt, system_message):
    try:
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ]
        response = llm.invoke(messages)
        return response.content
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        return None

# Create tables in SQLite from Excel sheets
def create_tables_from_sheets(sheets):
    for sheet_name, df in sheets.items():
        try:
            # Replace spaces in column names with underscores
            df.columns = df.columns.str.replace(' ', '_')
            # Save to SQLite table
            df.to_sql(sheet_name, conn, if_exists="replace", index=False)
            st.success(f"Table created for sheet: {sheet_name}")
        except Exception as e:
            st.error(f"An error occurred while creating the table {sheet_name}: {str(e)}")

# Upload and process documents
uploaded_files = st.file_uploader("Upload your Excel files", accept_multiple_files=True, type=["xlsx"])
if uploaded_files:
    sheets = load_excel_files(uploaded_files)
    st.session_state['sheets'] = sheets
    st.success("Documents uploaded and processed successfully.")
    create_tables_from_sheets(sheets)

# Add Data button
if st.button("Add Data"):
    sheets = st.session_state.get('sheets', None)
    if sheets:
        create_tables_from_sheets(sheets)
        st.success("Data added to the database.")
    else:
        st.error("No data to add. Please upload a document first.")

# SQL query generation section with example prompts
st.markdown("## Generate SQL queries based on the uploaded data or provided schema:")
prompt = st.text_area("Enter your prompt here (e.g., 'Select all data from the student performance table'):", height=100)
table_name = st.text_input("Enter the table name:")
system_message = (
    "You are a well-versed and proficient SQL programmer and you are excellent in generating and executing SQL queries. "
    "You provide thoughtful recommendations and insights on the table schema and detect any anomalies in the data such as null values, "
    "missing values, duplicates, data types, etc. You are an unbeatable anomaly detector and detect data issues and schema issues spontaneously."
)
if st.button("Generate SQL Query"):
    if prompt:
        if table_name in st.session_state['sheets']:
            df = st.session_state['sheets'][table_name]
            # Replace spaces in column names with underscores
            df.columns = df.columns.str.replace(' ', '_')
            # Create an in-memory SQLite database
            engine = create_engine("sqlite:///:memory:")
            # Convert DataFrame to a SQL table
            df.to_sql(table_name, engine, if_exists="replace", index=False)
            sql_result = chat_with_assistant(prompt, system_message)
            st.write(f"Generated SQL Query:\n{sql_result}")
            explanation_prompt = f"Explain how the following SQL query is executed:\n{sql_result}"
            explanation = chat_with_assistant(explanation_prompt, "You are a helpful assistant, SQL programmer, and data scientist.")
            st.write(f"Execution Explanation:\n{explanation}")
            st.session_state.chat_history.append({
                "user": prompt,
                "generator": sql_result
            })
        else:
            st.error(f"Table '{table_name}' not found in the uploaded data. Available tables are: {', '.join(st.session_state['sheets'].keys())}.")
    else:
        st.error("Please enter a prompt to generate an SQL query.")

# Adjust prompt box and buttons
st.markdown("""
    <style>
        .stTextArea textarea {
            width: 700px;
        }
        .stButton button {
            width: 200px;
        }
    </style>
""", unsafe_allow_html=True)

# Close SQLite connection when done
conn.close()