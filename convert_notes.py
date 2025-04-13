#!/usr/bin/env python3

import json
import os
import re
import sys
from datetime import datetime
from subprocess import call

# Path to the JSON file we'll read in:
INPUT_FILE = "./notes.json"

# Path to the directory where we'll save the converted notes:
OUTPUT_DIRECTORY = "./notes_converted/"

# Should the creation time of the created files be set to the creation
# time of the original notes?
# Will fail if you're not on a Mac, or don't have Xcode installed -
# in which case set this to False.
KEEP_ORIGINAL_CREATION_TIME = True

# Should the last-modified time of the created files be set to the
# last-modified time of the original notes?
KEEP_ORIGINAL_MODIFIED_TIME = True

TAG_POSITION = "end"  # "start" or "end"

# Link Config
# For configuration of a simplenote link to obsisdian-friendly link

# "wikilink"  ➜ [[File name]]
# "markdown"  ➜ [Title](File name.md)
LINK_STYLE = "wikilink" 
# Text when an id isn't found
PLACEHOLDER_FOR_MISSING = "MISSING-NOTE" 

def main():
    print("🔥 Script is running")
    ###################################################################
    # 1. Set-up and checking.

    if not os.path.exists(INPUT_FILE):
        sys.exit(f"There is no file at {INPUT_FILE}")

    if not os.path.isfile(INPUT_FILE):
        sys.exit(f"{INPUT_FILE} is not a file")

    if TAG_POSITION not in {"start", "end"}:
        sys.exit("Set TAG_POSITION as 'start' or 'end'.")

    if LINK_STYLE not in {"wikilink", "markdown"}:
        sys.exit("Set LINK_STYLE as 'wikilink' or 'markdown'.")

    if not os.path.isdir(OUTPUT_DIRECTORY):
        os.mkdir(OUTPUT_DIRECTORY)

    print("")

    ###################################################################
    # 2.  Read JSON once

    with open(INPUT_FILE, encoding="UTF-8") as json_file:
        try:
            data = json.load(json_file)
        except json.decoder.JSONDecodeError:
            sys.exit(f"Could not parse {INPUT_FILE}. Are you sure it's JSON?")

    if not isinstance(data, dict) or "activeNotes" not in data:
        sys.exit(f"{INPUT_FILE} doesn't look like a Simplenote export.")

    notes = data["activeNotes"]

    ###################################################################
    # 3.  PASS 1 – decide every file name up‑front

    filenames_used = {}        # filename → count
    id_to_filename = {}        # note_id  → filename

    def make_unique_filename(first_line: str) -> str:
        """Return a unique, sanitised *.md* file name for this first line."""
        base = first_line[:248] if len(first_line) > 248 else first_line
        base = base.replace("/", "").replace(":", "")
        candidate = base + ".md"
        if candidate in filenames_used:
            filenames_used[candidate] += 1
            candidate = f"{base} {filenames_used[candidate]}.md"
        else:
            filenames_used[candidate] = 1
        return candidate

    for note in notes:
        title = (note["content"].splitlines() or ["untitled"])[0]
        id_to_filename[note["id"]] = make_unique_filename(title)

    ###################################################################
    # 4.  Helper to rewrite a Simplenote URI to an Obsidian link

    import re
    sn_link_re = re.compile(
        r"\[([^\]]+)\]\(simplenote://note/([0-9a-f-]{36})\)", flags=re.I)

    def convert_link(match: re.Match) -> str:
        alias, target_id = match.group(1).strip(), match.group(2)
        if target_id not in id_to_filename:
            return f"{alias} ({PLACEHOLDER_FOR_MISSING}:{target_id})"

        target_file = id_to_filename[target_id]
        bare = target_file[:-3]   # strip ".md"

        if LINK_STYLE == "wikilink":
            if alias == bare:
                return f"[[{bare}]]"
            return f"[[{bare}|{alias}]]"
        else:  # ordinary markdown link
            return f"[{alias}]({target_file})"

    ###################################################################
    # 5.  PASS 2 – write the files, inserting tags and rewriting links

    for note in notes:
        lines = note["content"].splitlines()

        if not lines:
            print(f"Skipping empty note with ID {note['id']}")
            continue

        # insert tags
        if "tags" in note and note["tags"]:
            tags = ["#" + re.sub(r"\W+", "-", t) for t in note["tags"]]
            tag_line = " ".join(tags)
            if TAG_POSITION == "start":
                lines[1:1] = ["", tag_line]
            else:
                lines.extend(["", tag_line])

        # rewrite every Simplenote link in the whole note
        full_text = "\n".join(lines)
        full_text = sn_link_re.sub(convert_link, full_text)
        lines = full_text.split("\n")

        # file path from pass 1
        filename = id_to_filename[note["id"]]
        filepath = os.path.join(OUTPUT_DIRECTORY, filename)

        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, "w", encoding="UTF-8") as out:
            out.write("\n".join(lines))

        if KEEP_ORIGINAL_CREATION_TIME:
            creation_time = datetime.strptime(
                note["creationDate"], "%Y-%m-%dT%H:%M:%S.%fZ"
            ).strftime("%m/%d/%Y %H:%M:%S %p")
            call(["SetFile", "-d", creation_time, filepath])

        if KEEP_ORIGINAL_MODIFIED_TIME:
            modified_time = datetime.strptime(
                note["lastModified"], "%Y-%m-%dT%H:%M:%S.%fZ"
            ).timestamp()
            os.utime(filepath, (modified_time, modified_time))

    ###################################################################
    # 6.  Summary

    total = sum(filenames_used.values())
    print(f"\n{total} .md file{'s' if total != 1 else ''} "
          f"created in {OUTPUT_DIRECTORY}")
    
if __name__ == "__main__":
    main()
