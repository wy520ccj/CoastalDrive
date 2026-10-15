"""合成渐消减振器：低速斜率保持，阀开启后斜率降至四分之一；非实测。"""

from suspension_motion_reference import document as installation_document

from suspension_bench import DAMPER_DEFINITION, DAMPER_SCHEMA


def force(speed,kind):
    rate={"compression":5280./.75**2,"extension":2760./.75**2}[kind]
    value=abs(speed)
    return (1. if speed>=0. else -1.)*rate*(min(value,.05)+.25*max(value-.05,0.))


def document(*,bad_validation=False):
    value=installation_document()
    value.update(schema=DAMPER_SCHEMA,definition=DAMPER_DEFINITION)
    for corner in value["corners"].values():
        corner["damper_id"]="synthetic-asymmetric-digressive-20C"
        for row in corner["rows"]:
            if row["kind"]!="spring":
                row["force_N"]=force(row["input"],row["kind"])
                if bad_validation and row["split"]=="validation" and abs(row["input"])>.1:
                    row["force_N"]*=1.4
    return value
