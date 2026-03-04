import csv

input_file = 'input.csv'
output_file = 'output.csv'

with open(input_file, newline='', encoding='utf-8') as infile, \
     open(output_file, 'w', newline='', encoding='utf-8') as outfile:
    
    reader = csv.reader(infile)
    writer = csv.writer(outfile)

    for row in reader:
        if row:  # skip empty lines
            writer.writerow(row[:-1])  # remove last column
