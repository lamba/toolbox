import re
import sys

# Usage: python extract_matching_lines.py input.txt "your_regex_pattern"

# For example: 
#   To find all TSX function declarations
#   python3 extract_matching_lines.py /Users/lamba/Projects/js/charting_generic_enhanced/src/components/GenericDataChart.tsx "^\s*const [a-zA-Z_][a-zA-Z0-9_]*\s*=\s*\(.*\)" > ./GenericDataChart_functions.txt

if len(sys.argv) != 3:
    print("Usage: python extract_matching_lines.py <input_file> <regex_pattern>")
    sys.exit(1)

input_file = sys.argv[1]
pattern = sys.argv[2]
regex = re.compile(pattern)

with open(input_file, 'r', encoding='utf-8') as f:
    for line in f:
        if regex.search(line):
            print(line, end='')  # Avoid adding extra newlines
