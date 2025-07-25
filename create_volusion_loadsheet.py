# --- Import necessary libraries ---
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox
import chardet
import threading

# --- Validation: Allow only valid float values in text entries ---
def validate_float_input(new_value):
    if new_value == "":
        return True
    try:
        float(new_value)
        return True
    except ValueError:
        return False

# --- Add placeholder text to entry fields ---
def add_placeholder(entry, text):
    entry.configure(validate="none")
    
    if not entry.get():
        entry.insert(0, text)
        entry.config(fg="gray")

    def on_focus_in(event):
        if entry.get() == text:
            entry.delete(0, tk.END)
            entry.config(fg="black")

    def on_focus_out(event):
        if not entry.get():
            entry.insert(0, text)
            entry.config(fg="gray")

    entry.bind("<FocusIn>", on_focus_in)
    entry.bind("<FocusOut>", on_focus_out)

    # Re-enable validation
    entry.configure(validate="key")

def build_full_title(row):
    base_title = str(row.get('Title', '')).strip()
    options = []
    for opt_key in ['Option1 Value', 'Option2 Value', 'Option3 Value']:
        val = row.get(opt_key)
        if pd.notna(val):
            val_str = str(val).strip()
            if val_str and val_str.lower() != 'default title':
                options.append(val_str)
    return f"{base_title} - {' - '.join(options)}" if options else base_title

# --- Core file processing logic that runs in a background thread ---
def _process_file_worker(file_path):
    try:

        # Step 1: Read CSV File
        with open(file_path, 'rb') as f:
            raw_data = f.read()
            encoding = chardet.detect(raw_data)['encoding']

        df = pd.read_csv(file_path, encoding=encoding, low_memory=False)

        # Step 2: Get Parent Title
        productcode_to_title = df.set_index('productcode')['productname'].to_dict() # Create a mapping from productcode to productname
        df['Parent Title'] = df['ischildofproductcode'].map(productcode_to_title) # Create a new 'Parent Title' column

        # Step 2: Only include Visible Products
        child_product_codes = df['ischildofproductcode'].dropna().unique()
        df = df[~df['productcode'].isin(child_product_codes)]

        # Step 3: Add Multipliers
        try:
            jobber_multiplier = float(jobber_price_entry.get()) if jobber_price_entry.get() else 0.85 # get multiplers from text input
            dealer_multiplier = float(dealer_price_entry.get()) if dealer_price_entry.get() else 0.75
            oemwd_multiplier = float(oemwd_price_entry.get()) if oemwd_price_entry.get() else 0.675
        except ValueError:
            root.after(0, lambda: [
                status_label.config(text="Error: Invalid multiplier"),
                messagebox.showerror("Input Error", "Please enter valid numeric values for multipliers."),
            ])
            return
        df['Jobber Price'] = round(df['productprice'] * jobber_multiplier, 2) # calculate prices based on multipliers
        df['Dealer Price'] = round(df['productprice'] * dealer_multiplier, 2)
        df['OEM/WD Price'] = round(df['productprice'] * oemwd_multiplier, 2)
        price_columns = ['productprice', 'Jobber Price', 'Dealer Price', 'OEM/WD Price'] # convert prices to currency
        for col in price_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce') \
                    .map(lambda x: f"${x:,.2f}" if pd.notnull(x) else "")

        # Step 4: Create final list of columns
        final_variant_list = df.copy()
        final_column_list = [
            'productcode', 'productname', 'ischildofproductcode', 'Parent Title', 'productprice', 'Jobber Price',
            'Dealer Price', 'OEM/WD Price', 'length', 'width', 'productweight', 'Fitment',
            'productdescriptionshort', 'photourl', 'Image 2', 'Image 3', 'producturl'
        ]
        
        for col in final_column_list: # if column is not on csv file, fill in with '#N/A'
            if col not in final_variant_list.columns:
                final_variant_list[col] = '#N/A'
        final_variant_list = final_variant_list[final_column_list] # only include columns from column list

        final_variant_list.rename(columns={ # rename specific columns 
            'productcode': 'Part #',
            'productname': 'Full Title',
            'ischildofproductcode': 'Parent #',
            'Parent Title': 'Title',
            'productprice': 'Retail Price',
            'length': 'Length (in)',
            'width': 'Width (in)',
            'height': 'Height (in)',
            'productweight': 'Weight (in)',
            'productdescriptionshort': 'Description',
            'photourl': 'Image 1',
            'producturl': 'Product Link'
        }, inplace=True)

        # Step 5: Convert Image and Product URL columns into Excel-friendly hyperlinks
        hyperlink_columns = ['Image 1', 'Image 2', 'Image 3', 'Product Link']

        for col in hyperlink_columns:
            if col in final_variant_list.columns:
                final_variant_list[col] = final_variant_list[col].apply(
                    lambda x: f'=HYPERLINK("{x}")' if pd.notna(x) and str(x).strip().lower() != '#n/a' else '#N/A'
                )

        # Step 6: Fill all empty fields with '#N/A'
        final_variant_list.fillna("#N/A", inplace=True)

        # Step 7: Save the final processed CSV
        output_file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if output_file_path:
            final_variant_list.to_csv(output_file_path, index=False)
            root.after(0, lambda: [
                status_label.config(text="Processing complete."),
                messagebox.showinfo("Success", f"File processed and saved as {output_file_path}"),
            ])
        else:
            root.after(0, lambda: [
                status_label.config(text="Save cancelled."),
            ])

    except Exception as e:
        root.after(0, lambda: [
            status_label.config(text=f"Error: {e}"),
            messagebox.showerror("Error", f"An error occurred:\n{e}"),
        ])

def process_file(file_path):
    status_label.config(text="Processing...")
    threading.Thread(target=_process_file_worker, args=(file_path,), daemon=True).start()

def select_file():
    file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
    if file_path:
        process_file(file_path)

# --- GUI setup ---
root = tk.Tk()
root.title("Volusion CSV Processor (EMS)")

# --- Frame for multiplier entries ---
entry_frame = tk.Frame(root)
entry_frame.pack(padx=20, pady=20)

vcmd = (root.register(validate_float_input), '%P')

# --- Multiplers ---
tk.Label(entry_frame, text="Jobber Price Multiplier:").grid(row=0, column=0, sticky="e")
jobber_price_entry = tk.Entry(entry_frame, validate="key", validatecommand=vcmd)
jobber_price_entry.grid(row=0, column=1, padx=(10, 10), pady=5)
add_placeholder(jobber_price_entry, "0.85")

tk.Label(entry_frame, text="Dealer Price Multiplier:").grid(row=1, column=0, sticky="e")
dealer_price_entry = tk.Entry(entry_frame, validate="key", validatecommand=vcmd)
dealer_price_entry.grid(row=1, column=1, padx=(10, 10), pady=5)
add_placeholder(dealer_price_entry, "0.75")

tk.Label(entry_frame, text="OEM/WD Price Multiplier:").grid(row=2, column=0, sticky="e")
oemwd_price_entry = tk.Entry(entry_frame, validate="key", validatecommand=vcmd)
oemwd_price_entry.grid(row=2, column=1, padx=(10, 10), pady=5)
add_placeholder(oemwd_price_entry, "0.675")

# --- Process Button ---
process_button = tk.Button(root, text="Select and Process CSV File", command=select_file)
process_button.pack(pady=5)

# --- Status Label ---
status_label = tk.Label(root, text="", fg="blue")
status_label.pack(pady=5)

# --- Run the GUI event loop ---
root.mainloop()
