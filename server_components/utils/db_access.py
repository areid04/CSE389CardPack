import csv
# can change for db whenever?


# generic csv querey function
def query_csv(file_path, query_field, query_value):
    with open(file_path, mode='r', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row[query_field] == query_value:
                return row
    return None

def append_to_csv(file_path, fieldnames, data) -> bool:
    try:
        with open(file_path, mode='a', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writerow(data)        # append the new user to the csv file
        return True
    except Exception as e:
        print(f"Error appending to CSV: {e}")
        return False