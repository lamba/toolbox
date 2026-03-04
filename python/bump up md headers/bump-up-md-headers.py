import re

def promote_headers(md_text):
    def replace_header(match):
        hashes = match.group(1)
        space = match.group(2)
        if len(hashes) > 1:
            return '#' * (len(hashes) - 1) + space
        else:
            return match.group(0)  # Leave level-1 headers as is

    # Adjust only lines that start with Markdown headers
    return re.sub(r'^(#{1,6})(\s)', replace_header, md_text, flags=re.MULTILINE)

# --- Main ---
input_path = 'input.md'
output_path = 'output.md'

with open(input_path, 'r', encoding='utf-8') as f:
    content = f.read()

updated_content = promote_headers(content)

with open(output_path, 'w', encoding='utf-8') as f:
    f.write(updated_content)

print(f"Headers promoted and saved to {output_path}")
