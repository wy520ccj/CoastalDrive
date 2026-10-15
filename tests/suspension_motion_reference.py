"""同一部件/预压的合成安装几何；留出位置不参与插值，不代表实测K&C。"""

import copy

from suspension_preload_reference import document as installed_document

from suspension_bench import MOTION_DEFINITION, MOTION_SCHEMA
from suspension_installation import installation_curve


def document():
    value=installed_document()
    value.update(schema=MOTION_SCHEMA,definition=MOTION_DEFINITION)
    for corner in value["corners"].values():
        del corner["spring_motion_ratio"],corner["damper_motion_ratio"]
        corner["installation_source"]="analytic synthetic installation curve; NOT measured K&C"
        corner["installation_curve"]=[[q,.8*q+q*q,.75*q+.6*q*q] for q in (i/20 for i in range(-4,5))]
        corner["installation_validation"]=[[q,.8*q+q*q,.75*q+.6*q*q] for q in (i/40 for i in range(-7,8,2))]
    return value


def constant_document():
    curved=document()
    constant=installed_document()
    for wheel,corner in constant["corners"].items():
        axes=installation_curve(tuple(tuple(row) for row in curved["corners"][wheel]["installation_curve"]))
        corner["spring_motion_ratio"],corner["damper_motion_ratio"]=(axis.reference_ratio for axis in axes)
    return constant


def rejected_document():
    value=copy.deepcopy(document())
    value["corners"]["FL"]["installation_validation"][0][1]+=.003
    return value
