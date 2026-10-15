"""同一线性部件、仅安装压缩不同的合成夹具；不代表实测悬架。"""

from suspension_bench_reference import document as zero_document

from suspension_bench import INSTALLED_DEFINITION, INSTALLED_SCHEMA


def document(installed_compression=.016):
    value = zero_document()
    value.update(schema=INSTALLED_SCHEMA,definition=INSTALLED_DEFINITION)
    for corner in value["corners"].values():
        corner.update(spring_motion_ratio=.8,damper_motion_ratio=.75,
                      spring_installed_compression_m=installed_compression,
                      installation_source="synthetic reference installation at zero wheel travel; NOT measured")
        for row in corner["rows"]:
            rate = {"spring":75000.,"compression":5280./.75**2,"extension":2760./.75**2}[row["kind"]]
            row["force_N"] = rate*row["input"]
    return value
