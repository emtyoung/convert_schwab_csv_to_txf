import csv
import sys
from datetime import datetime
from io import StringIO
import os

def write_txf_header(output_file):
    """Write the TXF file header per V042 spec."""
    header = (
        "V042\n"  # TXF version
        "ACharles Schwab\n"  # Application/source identifier
        "D02/23/2025\n"  # Export date (today's date)
        "^\n"  # Start of transaction data
    )
    output_file.write(header)

def write_txf_record(output_file, description, date_acquired, date_sold, proceeds, basis, wash, record_type):
    """Write a single transaction record in TXF format per V042 spec."""
    # Format amounts to two decimal places
    proceeds_formatted = f"{float(proceeds):.2f}"
    basis_formatted = f"{float(basis):.2f}"
    wash_formatted = f"{float(wash):.2f}" if wash else "0.00"

    record = (
        "TD\n"  # Detailed record start
        f"{record_type}\n"  # Ref number (e.g., N321, N711)
        "C1\n"  # Copy number (always 1 for single 1099-B)
        "L1\n"  # Line number (always 1 per record)
        f"P{description}\n"  # Description field
        f"D{date_acquired}\n"  # Date acquired
        f"D{date_sold}\n"  # Date sold
        f"${basis_formatted}\n"  # Cost basis
        f"${proceeds_formatted}\n"  # Sales proceeds
    )
    if float(wash_formatted) != 0:  # Include wash sale only if non-zero
        record += f"${wash_formatted}\n"
    record += "^\n"  # Record terminator
    output_file.write(record)

def convert_schwab_csv_to_txf(csv_file_path):
    """Convert Schwab 1099-B CSV to TXF format, skipping rows before 1099-B header."""
    base, _ = os.path.splitext(csv_file_path)
    txf_file_path = base + '.TXF'
    total_proceeds = 0.0
    total_basis = 0.0
    total_wash = 0.0
    total_wash_adjusted_gain_loss = 0.0  # New variable for wash-adjusted gain/loss

    # Mapping of Form 8949 Codes to TXF record types
    form_8949_to_record_type = {
        "A": "N321",  # Short-term, basis reported
        "B": "N711",  # Short-term, basis not reported
        "C": "N712",  # Short-term, no 1099-B
        "D": "N323",  # Long-term, basis reported
        "E": "N713",  # Long-term, basis not reported
        "F": "N714",  # Long-term, no 1099-B
        "X": "N711"   # Unknown/other
    }

    with open(csv_file_path, 'r') as csv_file:
        lines = csv_file.readlines()

    # Find the 1099-B header row
    header_found = False
    header_index = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('"Description of property (Example 100 sh. XYZ Co.)"'):
            header_found = True
            header_index = i
            break

    if not header_found:
        raise ValueError("No Form 1099-B header found in the CSV file")

    # Extract the header and data rows
    header_row = lines[header_index].strip()
    data_rows = lines[header_index + 1:]  # All rows after the header

    # Create a StringIO object with the data rows and use DictReader
    csv_content = header_row + '\n' + ''.join(data_rows)
    csv_file_io = StringIO(csv_content)
    reader = csv.DictReader(csv_file_io)

    with open(txf_file_path, 'w') as txf_file:
        # Write TXF header
        write_txf_header(txf_file)

        # Process 1099-B transaction rows
        for row in reader:
            try:
                # Extract and clean data
                description = row.get("Description of property (Example 100 sh. XYZ Co.)", "").strip()
                date_acquired = row.get("Date acquired", "").strip()
                date_sold = row.get("Date sold or disposed", "").strip()
                proceeds = row.get("Proceeds", "0.00").replace(",", "").strip()
                basis = row.get("Cost or other basis", "0.00").replace(",", "").strip()
                wash = row.get("Wash sale loss disallowed", "0.00").replace(",", "").strip()
                form_8949_code = row.get("Form 8949 Code", "").strip().upper()

                # Remove dollar sign from wash sale value if present
                if wash.startswith("$"):
                    wash = wash[1:]

                # Validate monetary values
                try:
                    proceeds_float = float(proceeds)
                    basis_float = float(basis)
                    wash_float = float(wash) if wash else 0.0
                except ValueError:
                    raise ValueError("Invalid monetary value in row")

                # Calculate wash-adjusted gain/loss for this transaction
                wash_adjusted_gain_loss = proceeds_float - (basis_float - wash_float)
                total_wash_adjusted_gain_loss += wash_adjusted_gain_loss  # Accumulate total

                # Validate and format Date Sold
                try:
                    date_sold_formatted = datetime.strptime(date_sold, "%m/%d/%Y").strftime("%m/%d/%Y")
                except ValueError:
                    raise ValueError("Invalid Date sold or disposed format")

                # Handle Date Acquired
                if not date_acquired:  # Empty string
                    date_acquired_formatted = date_sold_formatted
                elif date_acquired.lower() == "various":
                    date_acquired_formatted = "VARIOUS"  # All uppercase
                else:
                    try:
                        date_acquired_formatted = datetime.strptime(date_acquired, "%m/%d/%Y").strftime("%m/%d/%Y")
                    except ValueError:
                        raise ValueError("Invalid Date acquired format")

                # Determine record type based solely on Form 8949 Code
                record_type = form_8949_to_record_type.get(form_8949_code, "N711")  # Default to N711 if missing/invalid

                # Update running totals
                total_proceeds += proceeds_float
                total_basis += basis_float
                total_wash += wash_float

                # Write the transaction to TXF
                write_txf_record(txf_file, description, date_acquired_formatted, date_sold_formatted, 
                               proceeds, basis, wash if wash_float != 0 else "", record_type)

            except ValueError as e:
                print(f"Error processing row {row}: {e}")
                continue
            except KeyError as e:
                print(f"Missing required column in row {row}: {e}")
                continue

        # Print totals for verification, including wash-adjusted gain/loss
        print("Verify these totals with your Schwab 1099-B summary:")
        print(f"Total Proceeds: ${total_proceeds:.2f}")
        print(f"Total Basis: ${total_basis:.2f}")
        print(f"Total Wash Sale Adjustments: ${total_wash:.2f}")
        print(f"Total Gain/Loss: ${total_proceeds - total_basis:.2f}")
        print(f"Wash-Adjusted Total Gain/Loss: ${total_wash_adjusted_gain_loss:.2f}")

    return txf_file_path

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <input_csv_file>")
        sys.exit(1)

    csv_file_path = sys.argv[1]

    try:
        txf_file_path = convert_schwab_csv_to_txf(csv_file_path)
        print(f"Conversion complete. TXF file saved as {txf_file_path}")
    except FileNotFoundError:
        print(f"Error: Input file {csv_file_path} not found.")
    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")