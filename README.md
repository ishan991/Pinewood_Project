# Pinewood Project Data Pipeline

## Setup and Installation

These instructions are for Windows PowerShell.

### 1. Clone the repository

```powershell
git clone https://github.com/ishan991/Pinewood_Project.git
cd Pinewood_Project
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
```

This creates an isolated Python environment for the project.

### 3. Activate the virtual environment

```powershell
.\.venv\Scripts\Activate.ps1
```

After activation, `(.venv)` should appear at the beginning of the PowerShell prompt.

If PowerShell blocks the activation script, run this temporary command and try again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

This changes the policy only for the current PowerShell session.

### 4. Upgrade pip

```powershell
python -m pip install --upgrade pip
```

This updates the Python package installer inside the virtual environment.

### 5. Install the project dependencies

```powershell
python -m pip install -r requirements.txt
```

This installs the packages listed in `requirements.txt`.

## Running the Data Pipeline

Make sure the virtual environment is active and the required raw input files are available under `data/raw/`. Then run:

```powershell
python pipeline/main.py
```

The pipeline processes the data in this order:

1. Raw CSV input from `data/raw/`
2. Bronze Parquet output in `data/bronze/`
3. Silver transformed output in `data/silver/`
4. Gold dimensional and fact output in `data/gold/`

The Bronze, Silver, and Gold output directories are created automatically when the pipeline runs successfully.

----

## Anomalies found for pcc_residents file

During the Bronze-to-Silver transformation for the pcc_residents dataset, we found mixed date formats in the source data.

- Some dates were in YYYY-MM-DD format, such as 2025-01-19.
- Some dates were in MM/DD/YYYY format, such as 03/28/2025.
- Some values were blank or invalid and needed to be preserved as missing values instead of being forced into a wrong date.

We resolved this by:

- parsing both supported formats with pandas,
- keeping blank values as blank/NaT,
- formatting all valid dates to yyyy-dd-mm before writing the Silver output.

This makes the date columns clean, consistent, and easier for Power BI to recognize as Date values.

## Anomalies found for Care level transformation

The care_level values were inconsistent across the source files, such as AL, Assisted, and Memory Care. We cleaned and standardized them into one final label format like Assisted Living, Independent Living, and Memory Care.

This keeps the dataset consistent and makes reporting easier in Power BI.

## Anomalies found for pcc_care_history file

During the Bronze-to-Silver transformation for the pcc_care_history dataset, the previous_level and new_level columns had inconsistent care labels across the source files.

- Some values were recorded as AL, Assisted, or Assisted Living.
- Other rows used IL, Independent, or Independent Living.
- Some values were stored as MC, Memory, or Memory Care.

We resolved this by standardizing all values into a single, consistent naming convention:

- Assisted Living
- Independent Living
- Memory Care

This keeps the care history records clean and makes it easier to track changes in resident care levels over time.

The change_date values also required cleaning because they were not always stored in the same format. Some dates were in YYYY-MM-DD and others in MM/DD/YYYY. We parsed both formats, converted valid dates to yyyy-dd-mm, and preserved invalid or blank values as missing dates where appropriate.

## Anomalies found for adp_shifts file

The hourly_rate field contained dictionary-like values stored as strings, and the correct rate depended on each employee role. We parsed the dictionary safely and extracted the matching rate per row. We then created Standard_Hourly_Rate and Total_Labor_Cost and removed the raw hourly_rate column from the Silver output.

## Employee ID mismatch between adp_shifts and pcc_incidents 

The `employee_id` column in `adp_shifts.parquet` and the `reported_by` column in `pcc_incidents.parquet` both appear to identify employees, but their values do not match.

- All 68,071 non-null `employee_id` values in `adp_shifts.parquet` are six characters long (617 distinct values), for example `E10104`.
- All 411 non-null `reported_by` values in `pcc_incidents.parquet` are five characters long (402 distinct values), for example `E1000`.
- There are no exact matches between the distinct values in the two columns.

This prevents us from reliably linking incidents to employee shift records. We will report this anomaly to the client and ask them to confirm whether the two columns use different employee ID formats or systems, whether either field has been truncated or transformed, and whether an authoritative employee ID crosswalk or mapping can be provided.

## Silver layer duplicate analysis

The eight files in `data/silver` contain 80,027 rows, and no exact duplicate rows were found when metadata columns were included.
After excluding metadata columns, 79,983 unique rows remained; only `yardi_leases.parquet` had duplicates, with 44 repeated rows reducing the file from 346 to 302 rows, duplicates were removed and only one row per duplicate was kept.

## Anomaly found in yardi_units file

The `yardi_units.parquet` dataset contains `community_id` values representing more than 14 communities, while the expected number of communities is 14.

Client clarification is required before handling the additional community IDs. Please confirm whether these IDs represent valid additional communities and should be included, or whether they are the result of an error in the source data and should be corrected or excluded.

## Anomalies found in hubspot_leads file

- Lead ID `HL385264` appears twice with conflicting community, source, dates, and status values, even though `lead_id` is defined as unique.
- Thirty-four leads have a `move_in_date` earlier than their `deposit_date`, which conflicts with the expected sales-funnel sequence and requires source-system validation. We will ask client for the correct lead if for `HL385264` and will confirm if there are cases where `move_in_date`  is earlier than their `deposit_date`.

---------------------------------------------------------------------------------

## DAX Measures

### Incident rate per 100 resident-days

This measure shows the number of incidents for every 100 days of resident care during the selected reporting period. It adjusts the incident count for both the number of active residents and the number of selected days, allowing periods or communities of different sizes to be compared more fairly. Because the resident table contains monthly snapshots, this version is intended for monthly reporting.

```DAX
Active Residents =
CALCULATE (
    DISTINCTCOUNT ( fact_residents[resident_key] ),
    fact_residents[status] = "Active"
)
```

```DAX
Selected Days =
COUNTROWS (
    VALUES ( dim_date[date] )
)
```

```DAX
Resident-Days =
[Active Residents] * [Selected Days]
```

```DAX
Total Incidents =
DISTINCTCOUNT ( fact_incidents[incident_id] )
```

```DAX
Incident Rate per 100 Resident-Days =
DIVIDE (
    [Total Incidents],
    [Resident-Days],
    0
) * 100
```

The final measure should be formatted as a decimal number rather than a percentage. For example, a result of `0.33` means that 0.33 incidents occurred for every 100 resident-days.

### Move-out rate percent for the trailing 90 days

This measure shows the percentage of the average active-resident population that moved out during the 90 days ending on the current report date. Both the move-out count and the average resident population use the same rolling period, making the measure suitable for identifying changes in resident turnover over time.

```DAX
Trailing 90-Day Move-Outs =
VAR EndDate =
    MAX ( dim_date[date] )
RETURN
    CALCULATE (
        DISTINCTCOUNT ( fact_leases[resident_key] ),
        REMOVEFILTERS ( dim_date ),
        fact_leases[move_out_date] > EndDate - 90,
        fact_leases[move_out_date] <= EndDate
    )
```

```DAX
Trailing 90-Day Average Active Residents =
VAR EndDate =
    MAX ( dim_date[date] )
VAR SnapshotDates =
    CALCULATETABLE (
        VALUES ( fact_residents[last_date] ),
        REMOVEFILTERS ( dim_date ),
        DATESINPERIOD (
            dim_date[date],
            EndDate,
            -90,
            DAY
        )
    )
RETURN
    AVERAGEX (
        SnapshotDates,
        CALCULATE (
            [Active Residents],
            REMOVEFILTERS ( dim_date )
        )
    )
```

```DAX
Trailing 90-Day Move-Out Rate =
DIVIDE (
    [Trailing 90-Day Move-Outs],
    [Trailing 90-Day Average Active Residents],
    0
)
```

The final move-out measure should be formatted as a percentage. For example, a result of `3.5%` means that the number of residents moving out during the trailing 90 days was equal to 3.5% of the average active-resident population during that period.

### Current Occupancy Percent

Current occupancy percent shows the share of available units that have an active lease on the selected monthly snapshot date. A lease is active when its move-in date is on or before the snapshot date and its move-out date is blank or on/after that date. Occupied units are counted distinctly so overlapping resident leases cannot cause the same unit to be counted more than once. The date filter is removed from the lease dates during the calculation so leases that began before the selected month but remain active are included.

```DAX
Total Units =
DISTINCTCOUNT ( fact_units[unit_key] )
```

```DAX
Occupied Units =
VAR SnapshotDate =
    MAX ( fact_units[snapshot_date] )
RETURN
    CALCULATE (
        DISTINCTCOUNT ( fact_leases[unit_key] ),
        REMOVEFILTERS ( dim_date ),
        FILTER (
            ALL (
                fact_leases[move_in_date],
                fact_leases[move_out_date]
            ),
            fact_leases[move_in_date] <= SnapshotDate
                && (
                    ISBLANK ( fact_leases[move_out_date] )
                    || fact_leases[move_out_date] >= SnapshotDate
                )
        )
    )
```

```DAX
Current Occupancy Percent =
DIVIDE (
    [Occupied Units],
    [Total Units],
    0
)
```

The final measure should be formatted as a percentage. For the June 1, 2025 snapshot, the current data contains 191 distinct occupied units out of 915 total units, producing an occupancy value of `20.87%`.

### Time Intelligence Measure: Rolling 90-Day Lead Conversion Performance

This time-intelligence calculation measures lead generation and conversion over the 90 calendar days ending on the current report date. The window moves forward for every date or month displayed in Power BI, making recent sales performance easier to compare without relying only on individual calendar months. It reports distinct leads created, distinct leads won, and the percentage of leads converted during the same rolling period. The `dim_date[date]` column should have an active relationship with `fact_hubspot_leads[created_date]`.

```DAX
Distinct Leads =
DISTINCTCOUNT (
    fact_hubspot_leads[lead_id]
)
```

Distinct count is used because lead ID `HL385264` appears more than once in the source data.

```DAX
Rolling 90-Day Leads =
VAR EndDate =
    MAX ( dim_date[date] )
RETURN
    CALCULATE (
        [Distinct Leads],
        REMOVEFILTERS ( dim_date ),
        DATESINPERIOD (
            dim_date[date],
            EndDate,
            -90,
            DAY
        )
    )
```

This measure counts distinct leads created during the 90-day period ending on the current visual date. `REMOVEFILTERS ( dim_date )` prevents a month displayed in a matrix from limiting the calculation to that calendar month alone.

```DAX
Rolling 90-Day Won Leads =
VAR EndDate =
    MAX ( dim_date[date] )
RETURN
    CALCULATE (
        [Distinct Leads],
        REMOVEFILTERS ( dim_date ),
        DATESINPERIOD (
            dim_date[date],
            EndDate,
            -90,
            DAY
        ),
        fact_hubspot_leads[status] = "Won"
    )
```

This measure uses the same rolling period but only counts leads whose status is `Won`.

```DAX
Rolling 90-Day Conversion Rate =
DIVIDE (
    [Rolling 90-Day Won Leads],
    [Rolling 90-Day Leads],
    0
)
```

The final conversion measure should be formatted as a percentage. For the period ending May 31, 2025, the 90-day window is March 3 through May 31 and contains 391 distinct leads, 69 won leads, and a conversion rate of `17.65%`. For the period ending June 30, 2025, the window is April 2 through June 30 and contains 438 distinct leads, 87 won leads, and a conversion rate of `19.86%`.

The recommended Power BI matrix uses lead source or community as rows, year-month as columns, and the three rolling measures as values. A suitable visual title is **Rolling 90-Day Lead Conversion Performance**. Each month represents the 90-day window ending on the last visible date of that month, not three complete calendar months.
