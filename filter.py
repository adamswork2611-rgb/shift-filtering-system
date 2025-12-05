import pandas as pd
from io import BytesIO

def find_header_row(file_content, column_identifier="Emp Name", max_rows_to_check=20):
    try:
        temp_df = pd.read_excel(
            BytesIO(file_content),
            header=None,
            nrows=max_rows_to_check
        )
    except Exception as e:
        return 11 

    for i, row in temp_df.iterrows():
        if column_identifier in row.astype(str).values:
            return i
    return 11

def get_excel(file_list):
    storage = []

    for file in file_list:    
        file_content = file.read()

        header_row_index = find_header_row(file_content, column_identifier="Emp Name")
        
        df = pd.read_excel(
            BytesIO(file_content),
            header=header_row_index, 
            dtype={"NRIC": str},
            parse_dates=["Last Clock-In Time"],
            )
        storage.append(df)
            
    if storage:
        return pd.concat(storage, ignore_index=True)  
    else: 
        return pd.DataFrame()

def filter_shift(data):

    def first_in_last_out(group):
        check_in = group["Transaction Event"].str.contains(r'\bIn\b', case=False, na=False)
        check_out = group["Transaction Event"].str.contains(r'\bOut\b', case=False, na=False)

        in_events = group[check_in]
        out_events = group[check_out]

        first_in = in_events.iloc[[0]] if not in_events.empty else pd.DataFrame()
        last_out = out_events.iloc[[-1]] if not out_events.empty else pd.DataFrame()

        in_out = pd.concat([first_in, last_out])
        if in_out.empty:
            return pd.DataFrame()
        
        return in_out.drop_duplicates().sort_values(by="DateTime")
    
    def skip_a_row(list):
        empty_row = pd.Series(index=list.columns, dtype=object).to_frame().T
        return pd.concat([list, empty_row], ignore_index=True)


    if data.empty:
        return pd.DataFrame()
    if "Date" not in data.columns or "Last Clock-In Time" not in data.columns:
        print("Missing Date or Last Clock-In Time column.")
        return pd.DataFrame()

    data["DateTime"] = pd.to_datetime(
        data["Date"].astype(str) + " " + data["Last Clock-In Time"].astype(str),
        errors="coerce",
    )
    data.dropna(subset=["DateTime"], inplace=True)
    
    if data.empty:
        return pd.DataFrame()

    data = (
        data.sort_values(by=["Emp Name", "DateTime"])
        .drop_duplicates(subset=["Emp Name", "DateTime", "Transaction Event"], keep="first")
        .reset_index(drop=True)
    )

    data["gap_hours"] = data.groupby("Emp Name")["DateTime"].diff().dt.total_seconds() / 3600

    data["new_shift"] = (data["gap_hours"] > 10) | (data["gap_hours"].isna())

    prev_event = data.groupby("Emp Name")["Transaction Event"].shift(1)
    
    is_prev_in = prev_event.str.contains(r'\bIn\b', case=False, na=False, regex=True)
    is_curr_out = data["Transaction Event"].str.contains(r'\bOut\b', case=False, na=False, regex=True)
    in_to_out_transition = is_prev_in & is_curr_out

    override_condition = (data["new_shift"] == True) & (data["gap_hours"] > 10) & in_to_out_transition
    data.loc[override_condition, "new_shift"] = False

    data["Shift ID"] = data.groupby("Emp Name")["new_shift"].cumsum()

    data = (
        data.groupby(["Emp Name", "Shift ID"], group_keys=False)
        .apply(first_in_last_out)
        .reset_index(drop=True)
    )

    data["Last Clock-In Time"] = data["DateTime"].dt.strftime("%H:%M:%S")
    data["Date"] = data["DateTime"].dt.strftime("%Y-%m-%d")
    data = data.drop(
        columns=["DateTime","gap_hours","new_shift"], 
        errors="ignore"
    )

    data = (
        data.groupby("Emp Name", group_keys=False)
        .apply(skip_a_row)
        .reset_index(drop=True)
        .iloc[:-1]
    )

    return data