"""从权威门线快照格式化分段；不推进或修正比赛状态。"""


def sector_times(splits):
    return tuple(end-start for start, end in zip((0., *splits), splits))


def split_feedback(race):
    if not race.splits:
        return "等待首个检查点\n" + ("对照出发时的整圈最佳" if race.reference_splits else "暂无同配置最佳分段")
    index = len(race.splits)-1
    seconds = sector_times(race.splits)[index]
    title = f"第{index+1}段  {seconds:.3f} s"
    if race.invalidated:
        return title+"\n本圈无效 · 不参与最佳比较"
    if not race.reference_splits:
        return title+"\n暂无同配置最佳分段"
    reference = sector_times(race.reference_splits)[index]
    cumulative = race.splits[index]-race.reference_splits[index]
    return title+f"  Δ {seconds-reference:+.3f}\n累计差 {cumulative:+.3f} s · 负值领先"


def result_columns(race):
    times = sector_times(race.splits)
    reference = sector_times(race.reference_splits)
    labels, values, deltas = ["路段"], ["本圈 / s"], ["比出发时最佳 / s"]
    for index, seconds in enumerate(times):
        labels.append(f"S{index+1}")
        values.append(f"{seconds:.3f}")
        deltas.append(f"{seconds-reference[index]:+.3f}" if reference and not race.invalidated else "—")
    return tuple("\n".join(column) for column in (labels, values, deltas))
