with open('app_old.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Line 2041 (0-indexed 2040) has the Paragraph with "Estimation des"
# Line 2042 (0-indexed 2041) has roi_fig_all_buf.seek(0)
# We need to insert an if check before line 2040 and indent lines 2040-2048

insert_pos = 2040  # 0-indexed position
indent_start = 2040
indent_end = 2049

# Insert the if statement
lines.insert(insert_pos, '    if roi_fig_all_buf is not None:\n')

# Now indent the following lines (they shifted by 1 due to insert)
for i in range(indent_start + 1, indent_end + 1 + 1):
    if i < len(lines) and not lines[i].strip().startswith('#'):
        lines[i] = '    ' + lines[i]

with open('app_old.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Fixed: Added None check for roi_fig_all_buf')
