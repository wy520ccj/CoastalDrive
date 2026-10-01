"""只读已保存轨迹，区分真实离开护栏与声学候选门槛。"""

import gzip
import json
from pathlib import Path

directory = Path(__file__).parent
report = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
analysis = {}
for trial in report["trials"]:
    with gzip.open(directory / trial["raw_jsonl_gz"], "rt", encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream]
    hit = trial["layered_hit_ticks"][0]
    counts = {"no_contact": 0, "impulse_only": 0, "speed_only": 0, "both": 0, "eligible": 0}
    for row in rows:
        if row["tick"] < hit:
            continue
        contacts = [contact for contact in row["contact_states"] if contact["material"] == "metal_barrier"]
        speed = any(contact["tangential_speed"] >= 1.6 for contact in contacts)
        impulse = any(contact["raw_impulse"] >= 25 for contact in contacts)
        eligible = any(contact["audio_candidate"] for contact in contacts)
        reason = ("no_contact" if not contacts else "eligible" if eligible else
                  "impulse_only" if speed and not impulse else "speed_only" if impulse and not speed else "both")
        counts[reason] += 1
    analysis[trial["name"]] = {
        "after_hit_reason_counts": counts,
        "physical_gaps_after_hit": [gap for gap in trial["gaps"]["rail_physical"]["all_gaps"] if gap["last_tick"] >= hit],
        "candidate_gaps_after_hit": [gap for gap in trial["gaps"]["rail_candidate"]["all_gaps"] if gap["last_tick"] >= hit],
    }
(directory / "qualification-analysis.json").write_text(json.dumps(analysis, indent=2)+"\n", encoding="utf-8")
print(json.dumps({name: {"reasons": values["after_hit_reason_counts"],
                        "physical_gaps_after_hit": values["physical_gaps_after_hit"]} for name, values in analysis.items()}, indent=2))
