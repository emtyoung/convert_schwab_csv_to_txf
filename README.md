# Convert Schwab 1099 CSV to TXF

This Python script converts a Schwab 1099 Composite and Year-End Summary CSV file into a TXF file that can be imported into tax software like TurboTax. Generated and modified with prompts to Grok 3.

## Usage

1.  **Download CSV:** Go to Schwab 1099 Dashboard and download 1099 Composite and Year-End Summary as a CSV file.
2.  **Run Script:** Execute the script, providing the input CSV file. Output will have the same name as the input file, but with .txf extension instead of .csv.

    python convert_schwab_csv_to_txf.py 1099.csv

3.  **Import TXF:** Import the generated TXF file into your tax software.

## Notes

Tested with Python 3.11 and TurboTax 2024.

## Disclaimer

This script is provided as-is, without any warranty. Use it at your own risk. It is recommended to review the generated TXF file before importing it into your tax software.
