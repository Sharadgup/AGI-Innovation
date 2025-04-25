# src/utils/data_analyzer_utils.py

import logging
import pandas as pd
import json
import os
import io # Needed for PDFReport potentially, though not used in current functions
from fpdf import FPDF # Make sure fpdf2 is installed: pip install fpdf2

# --- Data Analysis Helper Functions ---

def get_dataframe(filepath):
    """Safely reads CSV or Excel into Pandas DataFrame."""
    try:
        # Check file extension case-insensitively
        if filepath.lower().endswith('.csv'):
            df = pd.read_csv(filepath)
        elif filepath.lower().endswith('.xlsx'):
            # Specify engine if needed, though default often works
            df = pd.read_excel(filepath, engine='openpyxl')
        else:
            logging.warning(f"Unsupported file type for get_dataframe: {filepath}")
            return None # Return None for unsupported types

        # Basic type optimization (optional, can be refined)
        df = df.convert_dtypes()
        # Use os.path.basename for cleaner logging
        logging.info(f"Successfully read dataframe from '{os.path.basename(filepath)}', Shape: {df.shape}")
        return df

    except FileNotFoundError:
        logging.error(f"File not found at {filepath}")
        return None # Return None if file doesn't exist
    except pd.errors.EmptyDataError:
        logging.warning(f"File at {filepath} is empty.")
        # Return an empty DataFrame consistent with pandas behavior
        if filepath.lower().endswith('.csv'):
            return pd.DataFrame()
        elif filepath.lower().endswith('.xlsx'):
            # Reading an empty excel might need special handling or return empty df
             try:
                 # Try reading sheets, if none or all empty, return empty DF
                 xls = pd.ExcelFile(filepath, engine='openpyxl')
                 if not xls.sheet_names:
                     return pd.DataFrame()
                 # Check if first sheet has columns or data - crude check
                 first_sheet_df = xls.parse(xls.sheet_names[0])
                 if first_sheet_df.empty:
                     return pd.DataFrame()
                 # If we got here, maybe it's not truly empty, re-read normally?
                 # This part is tricky, maybe just return empty is safer.
                 logging.warning(f"Excel file {filepath} might not be truly empty but parsed as such initially. Returning empty DataFrame.")
                 return pd.DataFrame()
             except Exception as empty_excel_err:
                 logging.error(f"Error checking if excel file {filepath} is empty: {empty_excel_err}")
                 return None # Error during empty check
        else:
             return None # Should have been caught earlier
    except Exception as e:
        # Log the specific error and traceback for debugging
        logging.error(f"Error reading file {filepath}: {e}", exc_info=True)
        return None # Return None on other read errors

def get_column_info(df):
    """Generates summary info for DataFrame columns."""
    info = []
    if df is None or df.empty: # Handle None or empty DataFrame
        return info
    for col in df.columns:
        # Ensure JSON serializability for counts (convert numpy types)
        try:
            # Check if column exists before accessing dtype/isnull
            if col in df.columns:
                col_dtype = str(df[col].dtype)
                null_count = int(df[col].isnull().sum()) # Convert numpy.int64 to Python int
                info.append({
                    "name": col,
                    "dtype": col_dtype,
                    "null_count": null_count
                })
            else:
                 logging.warning(f"get_column_info: Column '{col}' not found during iteration (should not happen).")
        except Exception as col_info_err:
            logging.error(f"Error getting info for column '{col}': {col_info_err}")
            info.append({ "name": col, "dtype": "Error", "null_count": "Error" })
    return info

def generate_data_profile(df):
    """Creates a basic profile of the DataFrame."""
    if df is None:
        return {"row_count": 0, "col_count": 0, "column_info": [], "memory_usage": 0}
    if df.empty:
         return {"row_count": 0, "col_count": len(df.columns), "column_info": get_column_info(df), "memory_usage": 0}

    try:
        mem_usage = int(df.memory_usage(deep=True).sum())
    except Exception as mem_err:
        logging.warning(f"Could not calculate deep memory usage: {mem_err}. Using non-deep.")
        try:
             mem_usage = int(df.memory_usage(deep=False).sum())
        except Exception:
             mem_usage = -1 # Indicate error

    profile = {
        "row_count": len(df),
        "col_count": len(df.columns),
        "column_info": get_column_info(df),
        "memory_usage": mem_usage
    }
    # Add more profiling: duplicate rows, basic type summaries, etc.
    try:
         profile["duplicate_row_count"] = int(df.duplicated().sum())
    except Exception as dup_err:
         logging.warning(f"Could not calculate duplicate rows: {dup_err}")
         profile["duplicate_row_count"] = "Error"

    return profile

def generate_cleaning_recommendations(df):
    """Basic recommendation engine (can be significantly improved)."""
    if df is None: return ["DataFrame is not loaded."]
    if df.empty: return ["DataFrame is empty. No recommendations."]

    recommendations = []
    col_info = get_column_info(df) # Use helper to get consistent info
    total_rows = len(df)

    logging.debug(f"Generating recommendations for DF with {total_rows} rows.")

    # Duplicate Row Check first
    try:
        duplicate_count = int(df.duplicated().sum())
        if duplicate_count > 0:
            dup_percent = (duplicate_count / total_rows) * 100
            recommendations.append(f"Dataset contains **{duplicate_count} duplicate rows** ({dup_percent:.1f}%). Consider removing them using the 'Remove Duplicates' action.")
    except Exception as dup_err:
        logging.warning(f"Could not perform duplicate check: {dup_err}")


    for col in col_info:
        col_name = col['name']
        col_dtype = col['dtype']
        null_count = col.get('null_count') # Use .get for safety

        if null_count == "Error": # Skip if info couldn't be gathered
             recommendations.append(f"Could not analyze column **'{col_name}'** due to previous error.")
             continue
        if null_count is None: # Should not happen if get_column_info is correct
             logging.warning(f"Null count missing for column '{col_name}' in recommendations.")
             continue

        # Null Value Recommendations
        if null_count > 0:
            null_percent = (null_count / total_rows) * 100
            rec = f"Column **'{col_name}'** has {null_count} null values ({null_percent:.1f}%). Consider handling (e.g., fill, drop rows/column)."
            if null_percent > 70: # Higher threshold for dropping column suggestion
                 rec += " *High null percentage suggests dropping the column might be viable.*"
            elif null_percent > 30:
                 rec += " *Significant null percentage - investigate imputation or dropping rows carefully.*"
            recommendations.append(rec)

        # Data Type Specific Recommendations
        try:
            # Object/String Types
            if 'object' in col_dtype or 'string' in col_dtype:
                unique_vals = df[col_name].nunique()
                if unique_vals == 1 and total_rows > 1:
                     recommendations.append(f"Column **'{col_name}'** ({col_dtype}) has only **1 unique value**. It might be constant and potentially droppable.")
                elif unique_vals < 25 and total_rows > 50: # Arbitrary thresholds
                     recommendations.append(f"Column **'{col_name}'** ({col_dtype}) has low cardinality ({unique_vals} unique values). Consider converting to 'category' type for memory efficiency.")

                # Check sample for potential numeric strings (if not all null)
                non_null_series = df[col_name].dropna()
                if not non_null_series.empty:
                    sample_size = min(5, len(non_null_series))
                    sample = non_null_series.sample(sample_size)
                    # Improved check for numeric-like strings
                    numeric_like = all(isinstance(s, str) and s.replace('.', '', 1).replace('-', '', 1).strip().isdigit() for s in sample)
                    if numeric_like:
                        recommendations.append(f"Column **'{col_name}'** ({col_dtype}) contains values that look numeric (e.g., '{sample.iloc[0]}'). Consider converting to a numeric type if appropriate.")

                # Check for long strings
                try:
                    max_len = df[col_name].astype(str).str.len().max()
                    if pd.notna(max_len) and max_len > 250: # Increased threshold
                        recommendations.append(f"Column **'{col_name}'** ({col_dtype}) has long text entries (max length: {int(max_len)}). Review if full text is needed or if feature extraction/truncation is applicable.")
                except Exception as len_err:
                     logging.warning(f"Could not determine max length for column '{col_name}': {len_err}")


            # Numeric Types
            elif pd.api.types.is_numeric_dtype(df[col_name]) and null_count < total_rows:
                # Skewness check
                skewness = df[col_name].skew()
                if pd.notna(skewness) and abs(skewness) > 1.5: # Threshold for significant skew
                    recommendations.append(f"Numeric column **'{col_name}'** appears skewed (skewness: {skewness:.2f}). Consider transformation (e.g., log, sqrt) if model assumptions require normality.")

                # Basic outlier check (IQR method)
                q1 = df[col_name].quantile(0.25)
                q3 = df[col_name].quantile(0.75)
                if pd.notna(q1) and pd.notna(q3):
                    iqr = q3 - q1
                    lower_bound = q1 - 1.5 * iqr
                    upper_bound = q3 + 1.5 * iqr
                    outliers = df[(df[col_name] < lower_bound) | (df[col_name] > upper_bound)]
                    if not outliers.empty:
                        outlier_percent = (len(outliers) / (total_rows-null_count)) * 100 # Percent of non-nulls
                        recommendations.append(f"Numeric column **'{col_name}'** may have outliers ({len(outliers)} values or {outlier_percent:.1f}% outside 1.5*IQR range). Investigate further.")

            # Datetime Types (if detected)
            elif pd.api.types.is_datetime64_any_dtype(df[col_name]):
                 recommendations.append(f"Column **'{col_name}'** is datetime type. Consider extracting features like year, month, day, weekday, or calculating time differences if relevant.")

        except Exception as e:
            logging.warning(f"Error generating recommendations for column '{col_name}': {e}", exc_info=True)
            recommendations.append(f"Could not fully analyze column **'{col_name}'** due to an error.")


    if not recommendations:
        recommendations.append("No immediate cleaning recommendations based on basic checks. Data looks relatively clean, but deeper domain-specific validation may be needed.")

    return recommendations


def generate_gemini_insight_prompt(profile, cleaning_steps):
    """Generates a prompt for Gemini based on data profile and cleaning steps."""
    # Ensure profile data exists
    row_count = profile.get('row_count', 0)
    col_count = profile.get('col_count', 0)

    prompt = f"""Analyze the following data profile and applied cleaning steps. Provide key insights, potential issues, and recommendations for further analysis.

**Data Profile Summary:**
- Rows: {row_count}
- Columns: {col_count}
- Memory Usage: {profile.get('memory_usage', 'N/A')} bytes
- Column Details:
"""
    # Handle column info carefully, especially if row_count is 0
    column_info = profile.get('column_info', [])
    if column_info and row_count > 0:
        for col in column_info:
            null_count_val = col.get('null_count', 'N/A')
            null_perc_str = ""
            if isinstance(null_count_val, int):
                 null_perc = (null_count_val / row_count * 100)
                 null_perc_str = f" ({null_perc:.1f}%)"

            prompt += f"  - Name: {col.get('name', 'N/A')}, Type: {col.get('dtype', 'N/A')}, Nulls: {null_count_val}{null_perc_str}\n"
    elif column_info:
         for col in column_info: # Show columns even if no rows
              prompt += f"  - Name: {col.get('name', 'N/A')}, Type: {col.get('dtype', 'N/A')}, Nulls: N/A (0 rows)\n"
    else:
        prompt += "  (Column details not available)\n"

    # Add duplicate info if available
    if "duplicate_row_count" in profile:
         prompt += f"- Duplicate Rows Found: {profile['duplicate_row_count']}\n"


    if cleaning_steps:
        prompt += "\n**Cleaning Steps Applied:**\n"
        for i, step in enumerate(cleaning_steps):
             action = step.get('action', 'N/A')
             column = step.get('column', 'N/A')
             # Try to get meaningful detail from params
             params_detail = ""
             if 'method' in step.get('params', {}): params_detail = f"Method: {step['params']['method']}"
             elif 'new_type' in step.get('params', {}): params_detail = f"New Type: {step['params']['new_type']}"
             elif 'new_name' in step.get('params', {}): params_detail = f"New Name: {step['params']['new_name']}"
             elif 'subset' in step.get('params', {}): params_detail = f"Subset: {step['params']['subset']}"

             prompt += f"- Step {i+1}: Action='{action}', Column='{column}'"
             if params_detail: prompt += f", Details='{params_detail}'"
             # Optionally add timestamp: step.get('timestamp')
             prompt += "\n"
    else:
        prompt += "\n**Cleaning Steps Applied:** None\n"

    prompt += """
**Analysis Request:**

Based ONLY on the summary and cleaning steps provided above, provide the following in Markdown format:

1.  **Key Observations & Data Quality:**
    *   (e.g., Comment on data size, presence of duplicates. Highlight columns with high null percentages or potentially problematic types like 'object' if many exist. Note potential identifiers or categorical features based on names/types/cardinality hints if available. Mention any significant cleaning steps applied and their likely impact.)
2.  **Potential Analysis Directions:**
    *   (e.g., Based on column names/types, suggest possible target variables for prediction or key metrics for analysis. Identify potential relationships to explore between numeric or numeric/categorical columns. Suggest if the data seems suitable for time series analysis, classification, regression, etc.)
3.  **Recommendations for Next Steps:**
    *   (e.g., Suggest specific visualizations: histograms/boxplots for numeric distributions, bar charts for categoricals, scatter plots for relationships. Recommend statistical tests like correlation for numeric pairs, t-tests/ANOVA if comparing groups seems relevant. Suggest feature engineering ideas like date part extraction, binning numerics, or creating interaction terms based *only* on column names/types.)

**Important:** Focus on actionable insights derived *strictly* from the provided profile and cleaning information. Do not invent data points or assume external knowledge about the dataset's domain. Keep the response concise and focused on data structure and potential.
"""
    return prompt


# --- PDF Report Generation Class ---
# Uses fpdf2 (pip install fpdf2)
class PDFReport(FPDF):
    """Class to generate PDF reports for data analysis summaries."""
    def header(self):
        """Adds a header to each page."""
        # Arial bold 15
        self.set_font('Arial', 'B', 15) # Standard font
        # Calculate width of title and position
        title_w = self.get_string_width('Data Analysis Report') + 6
        doc_w = self.w
        self.set_x((doc_w - title_w) / 2)
        # Colors of frame, background and text
        # self.set_draw_color(0, 80, 180)
        # self.set_fill_color(230, 230, 0)
        # self.set_text_color(220, 50, 50)
        # Thickness of frame (1 mm)
        # self.set_line_width(1)
        # Title
        self.cell(title_w, 10, 'Data Analysis Report', border=0, ln=1, align='C', fill=False) # No border/fill
        # Line break
        self.ln(10)

    def footer(self):
        """Adds a footer to each page."""
        # Position at 1.5 cm from bottom
        self.set_y(-15)
        # Arial italic 8
        self.set_font('Arial', 'I', 8)
        # Text color in gray
        self.set_text_color(128)
        # Page number
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

    def chapter_title(self, title):
        """Adds a styled chapter title."""
        # Arial 12
        self.set_font('Arial', 'B', 12)
        # Background color
        self.set_fill_color(200, 220, 255)
        # Title
        self.cell(0, 6, title, ln=1, fill=True, align='L')
        # Line break
        self.ln(4)

    def chapter_body(self, body_text):
        """Adds text content to a chapter."""
        # Times 10
        self.set_font('Times', '', 10) # Use Times for body text
        # Handle potential encoding issues - encode to latin-1, replacing unknown chars
        try:
            safe_text = str(body_text).encode('latin-1', 'replace').decode('latin-1')
            # Output justified text
            self.multi_cell(0, 5, safe_text)
        except Exception as e:
             logging.error(f"Error encoding chapter body text for PDF: {e}")
             self.set_font('Arial', 'I', 8) # Fallback font
             self.multi_cell(0, 5, "[Error displaying text due to encoding issue]")
        # Line break
        self.ln()
        # Mention in italics
        # self.set_font('', 'I')
        # self.cell(0, 5, '(end of excerpt)')

    def add_table(self, header, data, col_widths=None):
         """Adds a formatted table to the PDF."""
         # Setup
         self.set_font('Arial', 'B', 9) # Header font
         self.set_fill_color(224, 235, 255) # Header background
         self.set_text_color(0) # Black text
         self.set_draw_color(150) # Light grey border
         self.set_line_width(0.3)
         page_width = self.w - 2 * self.l_margin # Available width

         # Calculate Column Widths
         num_cols = len(header)
         if num_cols == 0: return # Cannot add empty table
         if col_widths is None: # Default equal widths
             default_col_width = page_width / num_cols
             col_widths = [default_col_width] * num_cols
         elif sum(col_widths) > (page_width + 0.1): # Allow slight overflow due to float precision
              logging.warning(f"PDF table column widths ({sum(col_widths):.1f}mm) exceed page width ({page_width:.1f}mm). Adjusting.")
              scale_factor = page_width / sum(col_widths) if sum(col_widths) > 0 else 1
              col_widths = [w * scale_factor for w in col_widths]

         # Header Row
         for i, h in enumerate(header):
             try:
                 safe_h = str(h).encode('latin-1', 'replace').decode('latin-1')
                 # Truncate header if too long? Probably not needed.
                 self.cell(col_widths[i], 7, safe_h, border=1, align='C', fill=True)
             except Exception as e:
                  logging.error(f"Error encoding header '{h}' for PDF table: {e}")
                  self.cell(col_widths[i], 7, '[ERR]', border=1, align='C', fill=True)
         self.ln() # Move to next line after header

         # Data Rows
         self.set_font('Arial', '', 8) # Data font
         self.set_fill_color(255) # White background for data rows
         fill = False # Flag for alternating row colors (currently off)
         for row_idx, row in enumerate(data):
             row_items = list(row)
             # Ensure row has the correct number of items, padding if necessary
             if len(row_items) < num_cols:
                 row_items.extend([''] * (num_cols - len(row_items)))
             elif len(row_items) > num_cols:
                  row_items = row_items[:num_cols] # Truncate extra items

             for i, item in enumerate(row_items):
                 try:
                     item_str = str(item).encode('latin-1', 'replace').decode('latin-1')
                     # Simple heuristic for max chars based on width (adjust multiplier)
                     # Approx 2 chars per mm? Varies with font.
                     max_chars = int(col_widths[i] * 1.8) if col_widths[i] > 3 else 1
                     display_item = (item_str[:max_chars-3] + '...') if len(item_str) > max_chars else item_str
                     # Align left for text generally
                     align = 'L'
                     # Maybe right-align numbers? Crude check.
                     if item_str.replace('.', '', 1).replace('-', '', 1).isdigit(): align = 'R'
                     self.cell(col_widths[i], 6, display_item, border=1, align=align, fill=fill)
                 except Exception as e:
                      logging.error(f"Error encoding item '{item}' (Row {row_idx}, Col {i}) for PDF table cell: {e}")
                      self.cell(col_widths[i], 6, '[ERR]', border=1, align='L', fill=fill)
             self.ln() # Move to next line after row
             # fill = not fill # Toggle fill for alternate row shading if desired
         self.ln() # Add space after table

    def add_json_block(self, title, json_data):
        """Adds a formatted JSON block to the PDF."""
        # Title for the block
        self.set_font('Arial', 'B', 10)
        self.set_text_color(0)
        self.cell(0, 6, title, ln=1, align='L')
        self.ln(2)
        # Use Courier for JSON, smaller font
        self.set_font('Courier', '', 8)
        try:
            # Pretty print JSON, handle non-serializable types with default=str
            json_str = json.dumps(json_data, indent=2, default=str)
            # Encode safely for latin-1
            safe_json_str = json_str.encode('latin-1', 'replace').decode('latin-1')
            # Use multi_cell to handle line breaks
            self.multi_cell(0, 4, safe_json_str) # Adjust line height (4)
        except Exception as e:
            logging.error(f"Error formatting JSON block '{title}' for PDF: {e}")
            self.set_font('Arial', 'I', 8) # Fallback font
            self.multi_cell(0, 5, "[Error displaying JSON data]")
        self.ln(5) # Add space after the block