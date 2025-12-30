def get_matched_entries_with_following(filepath, keyword, n_following):
    keyword = keyword.lower()
    entries = []

    with open(filepath, "r") as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i]
        if keyword in line.lower():
            entry = [line]  # start new entry with matched line

            # Add up to n_following lines that do NOT contain keyword
            for j in range(1, n_following + 1):
                if i + j >= len(lines):
                    break
                next_line = lines[i + j]
                if keyword in next_line.lower():
                    break
                entry.append(next_line)

            entries.append(entry)
            i += len(entry)  # skip over the matched + following lines
        else:
            i += 1

    return entries


# Example usage:
matched_entries = get_matched_entries_with_following(
    "logs/job-scheduler.job.13.log", "Total inference features", 25
)
for idx, entry in enumerate(matched_entries):
    print(f"Entry {idx + 1}:")
    print("".join(entry))
    print("=" * 40)