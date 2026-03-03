import csv
import sys
from datetime import datetime
from io import StringIO
import os

def write_txf_header(output_file):
    """Write the TXF file header per V042 spec."""
    # Get today's date in MM/DD/YYYY format
    today = datetime.now().strftime("%m/%d/%Y")
    header = (
        "V042\n"  # TXF version
        "AFidelity Investments\n"  # Application/source identifier
        f"D{today}\n"  # Export date (today's date)
        "^\n"  # Start of transaction data
    )
    output_file.write(header)

def write_txf_record(output_file, description, date_acquired, date_sold, proceeds, basis, wash, record_type):
    """Write a single transaction record in TXF format per V042 spec."""
    # Format amounts to two decimal places, except basis of 0
    proceeds_formatted = f"{float(proceeds):.2f}"
    basis_formatted = "" if float(basis) == 0 else f"{float(basis):.2f}"  # Empty if basis is 0
    wash_formatted = f"{float(wash):.2f}" if wash else "0.00"

    record = (
        "TD\n"  # Detailed record start
        f"{record_type}\n"  # Ref number (e.g., N321, N711)
        "C1\n"  # Copy number (always 1 for single 1099-B)
        "L1\n"  # Line number (always 1 per record)
        f"P{description}\n"  # Description field
        f"D{date_acquired}\n"  # Date acquired (empty if not provided)
        f"D{date_sold}\n"  # Date sold
        f"${basis_formatted}\n"  # Cost basis (empty $ if 0)
        f"${proceeds_formatted}\n"  # Sales proceeds
    )
    if float(wash_formatted) != 0:  # Include wash sale only if non-zero
        record += f"${wash_formatted}\n"
    record += "^\n"  # Record terminator
    output_file.write(record)

def convert_fidelity_csv_to_txf(csv_file_path):
    """Convert Fidelity 1099-B CSV to TXF format."""
    base, _ = os.path.splitext(csv_file_path)
    txf_file_path = base + '.TXF'
    total_proceeds = 0.0
    total_basis = 0.0
    total_wash = 0.0
    total_wash_adjusted_gain_loss = 0.0

    # Mapping of Term + Covered status to TXF record types
    # Based on IRS Form 8949 codes where:
    # A/D = basis reported to IRS, B/E = basis not reported
    term_covered_to_record_type = {
        ("SHORT TERM", "COVERED"): "N321",    # Code A: Short-term, basis reported
        ("SHORT TERM", "NONCOVERED"): "N711",  # Code B: Short-term, basis not reported
        ("LONG TERM", "COVERED"): "N323",      # Code D: Long-term, basis reported
        ("LONG TERM", "NONCOVERED"): "N713",   # Code E: Long-term, basis not reported
    }

    # Read the CSV file - Fidelity uses carriage return (\r) as line separator
    with open(csv_file_path, 'r', newline='') as csv_file:
        content = csv_file.read()

    # Split by carriage return to get all rows
    lines = content.split('\r')

    # Find the 1099-B-Detail section header row
    detail_header_index = None
    for i, line in enumerate(lines):
        if "1099-B-Detail" in line:
            detail_header_index = i
            break

    if detail_header_index is None:
        raise ValueError("No Form 1099-B-Detail header found in the CSV file")

    # The 1099-B-Detail header row has the column structure
    # Transaction data starts at row index 5 (relative to start of file)
    # Look for data rows after the header

    with open(txf_file_path, 'w') as txf_file:
        # Write TXF header
        write_txf_header(txf_file)

        # Process 1099-B transaction rows
        # Transaction rows typically start at index 5, but we verify they have data
        transaction_rows = []
        for i in range(5, len(lines)):
            line = lines[i]
            # Skip rows that are too short to be transactions
            if len(line) < 200:
                continue

            # Try to parse as CSV
            try:
                csv_io = StringIO(line)
                reader = csv.reader(csv_io)
                row = next(reader)

                # Verify it's a transaction row (needs to have at least 22 columns)
                if len(row) < 22:
                    continue

                # Get description from column 8
                description = row[8].strip() if len(row) > 8 else ""
                date_sold = row[12].strip() if len(row) > 12 else ""

                # Skip header rows (column 8 starts with "1099-B-1a" for headers)
                if description.startswith("1099-B-1a"):
                    continue

                # Skip rows missing description or empty date sold (likely subtotal/empty rows)
                if not description or not date_sold or not date_sold.strip():
                    continue

                transaction_rows.append(row)
            except (csv.Error, StopIteration):
                continue

        for row in transaction_rows:
            try:
                # Extract and clean data from Fidelity columns
                description = row[8].strip() if len(row) > 8 else ""
                date_acquired = row[11].strip() if len(row) > 11 else ""
                date_sold = row[12].strip() if len(row) > 12 else ""
                proceeds = row[13].strip() if len(row) > 13 else "0.00"
                basis = row[14].strip() if len(row) > 14 else "0.00"
                wash = row[16].strip() if len(row) > 16 else "0.00"
                term = row[21].strip() if len(row) > 21 else ""
                covered = row[22].strip() if len(row) > 22 else ""

                # Clean monetary values: remove leading zeros from Fidelity's format like "0000000000008180.00"
                proceeds = proceeds.lstrip('0') or "0.00"
                basis = basis.lstrip('0') or "0.00"
                wash = wash.lstrip('0') or "0.00"

                # Validate monetary values
                try:
                    proceeds_float = float(proceeds)
                    basis_float = float(basis)
                    wash_float = float(wash) if wash else 0.0
                except ValueError:
                    raise ValueError("Invalid monetary value in row")

                # Calculate wash-adjusted gain/loss: (proceeds - basis) + wash
                wash_adjusted_gain_loss = (proceeds_float - basis_float) + wash_float
                total_wash_adjusted_gain_loss += wash_adjusted_gain_loss

                # Validate and format Date Sold (Fidelity format: MM/DD/YY)
                try:
                    # Parse MM/DD/YY and convert to MM/DD/YYYY
                    date_obj = datetime.strptime(date_sold, "%m/%d/%y")
                    date_sold_formatted = date_obj.strftime("%m/%d/%Y")
                except ValueError:
                    raise ValueError(f"Invalid Date sold or disposed format: {date_sold}")

                # Handle Date Acquired
                if not date_acquired:  # Empty string
                    date_acquired_formatted = ""  # Output empty date in TXF
                elif date_acquired.lower() == "various":
                    date_acquired_formatted = "VARIOUS"  # All uppercase
                else:
                    try:
                        # Parse MM/DD/YY and convert to MM/DD/YYYY
                        date_obj = datetime.strptime(date_acquired, "%m/%d/%y")
                        date_acquired_formatted = date_obj.strftime("%m/%d/%Y")
                    except ValueError:
                        raise ValueError(f"Invalid Date acquired format: {date_acquired}")

                # Determine record type based on Term and Covered status
                record_type = term_covered_to_record_type.get((term, covered), "N711")  # Default to N711 if missing

                # Update running totals
                total_proceeds += proceeds_float
                total_basis += basis_float
                total_wash += wash_float

                # Write the transaction to TXF
                write_txf_record(txf_file, description, date_acquired_formatted, date_sold_formatted,
                               proceeds, basis, wash if wash_float != 0 else "", record_type)

            except ValueError as e:
                print(f"Error processing row: {e}")
                continue
            except IndexError as e:
                print(f"Missing required column: {e}")
                continue

        # Print totals for verification, including wash-adjusted gain/loss
        print("Verify these totals with your Fidelity 1099-B summary:")
        print(f"Total Proceeds: ${total_proceeds:.2f}")
        print(f"Total Basis: ${total_basis:.2f}")
        print(f"Total Gain/Loss: ${total_proceeds - total_basis:.2f}")
        print(f"Total Wash Sale Adjustments: ${total_wash:.2f}")
        print(f"Wash-Adjusted Total Gain/Loss: ${total_wash_adjusted_gain_loss:.2f}")

    return txf_file_path

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <input_csv_file>")
        sys.exit(1)

    csv_file_path = sys.argv[1]

    try:
        txf_file_path = convert_fidelity_csv_to_txf(csv_file_path)
        print(f"Conversion complete. TXF file saved as {txf_file_path}")
    except FileNotFoundError:
        print(f"Error: Input file {csv_file_path} not found.")
    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
