# Script to parse CSV files and run SQL stored procedures to import them into the reporting Database.

import os
import csv
import pyodbc
import logging
import pandas as pd
from typing import List, Tuple, Dict, Any, Optional

from constants import DOWNLOADS_DIR, LOGS_DIR

log_file = os.path.join(LOGS_DIR, "csv_compile_and_upload.log")
logging.basicConfig(
    handlers=[
        logging.FileHandler(log_file, mode="a", encoding="utf-8"),
        logging.StreamHandler(),
    ],
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def clean_csv_files(_csv_filesnames: List[Optional[str]]):
    for file in _csv_filesnames:
        if file is None:
            continue

        file_path = os.path.join(DOWNLOADS_DIR, file)

        if not os.path.exists(file_path):
            logger.warning(f"CSV file not found at {file_path}.")

        try:
            df = pd.read_csv(file_path)

            if "EMAIL" not in df.columns:
                logger.warning(f"EMAIL column not found in {file}.")
                continue

            initial_count = len(df)
            df = df.dropna(subset=["EMAIL"])  # Remove rows with empty email
            df = df[df["EMAIL"].str.strip() != ""]  # Remove empty strings
            final_count = len(df)

            df.to_csv(file_path, index=False)
            logger.info(
                f"Cleaned {file}: Removed {initial_count - final_count} rows with null emails."
            )

        except Exception as err:
            logger.error(f"Error cleaning {file}: {err}")


# If file tempout exists, delete it
if os.path.exists("tempout.txt"):
    os.remove("tempout.txt")
else:
    print("The file does not exist")


writer = csv.writer(open("tempout.txt", "a", newline=""))
# will write to a text file - preventing the inadventant opening of the output file as a CSV IF there is an existing output file

path = "c://csv"
# path to stored csv files - should be the same directory as the python file.

files_in_dir = os.listdir(path)
# for files in os.walk(directory):
for file in files_in_dir:
    if file.endswith(".csv"):
        f = open(file, "r")
        coursenum = format(file[0:4])
        reader = csv.reader(f)
        for row in reader:
            row.append(coursenum)
            writer.writerow(row)


# Purge garbage rows from data
with open("tempout.txt", "r") as input:
    with open("temp.txt", "w") as output:
        # iterate all lines from file
        for line in input:
            # if substring contain in a line then don't write it
            if "Last Name,Email," not in line.strip("\n"):
                output.write(line)

# replace file with original name
os.replace("temp.txt", "out.txt")


# Define server and database parameters
# This server is offline - so this part will fail/have to be updated.
server = "3.14.132.71"
database = "TACReportDB"
username = "grafana"
password = "SBSC_Tr@ining_SQL_PoC"
driver = "{ODBC Driver 17 for SQL Server}"

# Create a new SQL connection
try:
    cnxn = pyodbc.connect(
        "DRIVER="
        + driver
        + ";SERVER="
        + server
        + ";DATABASE="
        + database
        + ";UID="
        + username
        + ";PWD="
        + password
    )
    cursor = cnxn.cursor()
    cursor.execute("EXEC dbo.pBulkMerge")
    cnxn.commit()
    cursor.execute("EXEC dbo.pBulkHandsON")
    cnxn.commit()

    print("Successfully connected to the server and executed the stored procedure.")
except pyodbc.Error as ex:
    sqlstate = ex.args[1]
    print(sqlstate)
finally:
    cnxn.close()
