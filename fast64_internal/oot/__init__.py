import bpy
from .exporter.hackeroot.scene_bootup import OOTBootupSceneOptions
from bpy.utils import register_class, unregister_class
from .general import oot_obj_register, oot_obj_unregister
from .panel.properties.general import oot_obj_panel_register, oot_obj_panel_unregister
from .panel.viewport.skeleton.classes import OOTSkeletonImportSettings, OOTSkeletonExportSettings
from .oot_utility import oot_utility_register, oot_utility_unregister
from .panel.viewport.display_list.classes import OOTDLExportSettings, OOTDLImportSettings
from .panel.viewport.file_settings import file_register, file_unregister
from .panel.properties.collision import oot_col_panel_register, oot_col_panel_unregister
from .collision.classes import oot_col_register, oot_col_unregister
from .panel.properties.f3d import oot_dl_writer_panel_register, oot_dl_writer_panel_unregister
from .f3d.classes import oot_dl_writer_register, oot_dl_writer_unregister

from .panel.viewport.display_list import (
    dl_writer_panel_register,
    dl_writer_panel_unregister,
    dl_writer_register,
    dl_writer_unregister,
)

from .panel.viewport.collision import (
    collision_panel_register,
    collision_panel_unregister,
    collision_register,
    collision_unregister,
)

from .panel.viewport.scene import (
    oot_level_panel_register,
    oot_level_panel_unregister,
    oot_level_register,
    oot_level_unregister,
)

from .panel.viewport.animation import (
    oot_anim_panel_register,
    oot_anim_panel_unregister,
    oot_anim_register,
    oot_anim_unregister,
)

from .panel.viewport.tools import (
    oot_operator_panel_register,
    oot_operator_panel_unregister,
    oot_operator_register,
    oot_operator_unregister,
)

from .panel.viewport.cutscene import (
    oot_cutscene_panel_register,
    oot_cutscene_panel_unregister,
    oot_cutscene_register,
    oot_cutscene_unregister,
)

from .panel.viewport.skeleton import (
    skeletonPanelRegister,
    skeletonPanelUnregister,
    skeletonRegister,
    skeletonUnregister,
)

from .panel.properties.skeleton import (
    oot_skeleton_panel_register,
    oot_skeleton_panel_unregister,
    oot_skeleton_register,
    oot_skeleton_unregister,
)

from .panel.properties.spline import (
    oot_spline_panel_register,
    oot_spline_panel_unregister,
    oot_spline_register,
    oot_spline_unregister,
)


class OOT_Properties(bpy.types.PropertyGroup):
    """Global OOT Scene Properties found under scene.fast64.oot"""

    version: bpy.props.IntProperty(name="OOT_Properties Version", default=0)
    hackerFeaturesEnabled: bpy.props.BoolProperty(name="Enable HackerOOT Features")
    bootupSceneOptions: bpy.props.PointerProperty(type=OOTBootupSceneOptions)
    DLExportSettings: bpy.props.PointerProperty(type=OOTDLExportSettings)
    DLImportSettings: bpy.props.PointerProperty(type=OOTDLImportSettings)
    skeletonExportSettings: bpy.props.PointerProperty(type=OOTSkeletonExportSettings)
    skeletonImportSettings: bpy.props.PointerProperty(type=OOTSkeletonImportSettings)


oot_classes = (OOT_Properties,)


def oot_panel_register():
    oot_operator_panel_register()
    oot_dl_writer_panel_register()
    oot_col_panel_register()
    oot_obj_panel_register()
    oot_level_panel_register()
    oot_spline_panel_register()
    oot_anim_panel_register()
    oot_skeleton_panel_register()
    oot_cutscene_panel_register()
    skeletonPanelRegister()
    collision_panel_register()
    dl_writer_panel_register()


def oot_panel_unregister():
    oot_operator_panel_unregister()
    oot_col_panel_unregister()
    oot_obj_panel_unregister()
    oot_level_panel_unregister()
    oot_spline_panel_unregister()
    oot_dl_writer_panel_unregister()
    oot_anim_panel_unregister()
    oot_skeleton_panel_unregister()
    oot_cutscene_panel_unregister()
    skeletonPanelUnregister()
    collision_panel_unregister()
    dl_writer_panel_unregister()


def oot_register(registerPanels):
    oot_operator_register()
    oot_utility_register()
    oot_col_register()  # register first, so panel goes above mat panel
    oot_obj_register()
    oot_level_register()
    oot_spline_register()
    oot_dl_writer_register()
    oot_anim_register()
    oot_skeleton_register()
    oot_cutscene_register()
    skeletonRegister()
    collision_register()
    dl_writer_register()
    file_register()

    for cls in oot_classes:
        register_class(cls)

    if registerPanels:
        oot_panel_register()


def oot_unregister(unregisterPanels):
    for cls in reversed(oot_classes):
        unregister_class(cls)

    oot_operator_unregister()
    oot_utility_unregister()
    oot_col_unregister()
    oot_obj_unregister()
    oot_level_unregister()
    oot_spline_unregister()
    oot_dl_writer_unregister()
    oot_anim_unregister()
    oot_skeleton_unregister()
    oot_cutscene_unregister()
    skeletonUnregister()
    collision_unregister()
    dl_writer_unregister()
    file_unregister()

    if unregisterPanels:
        oot_panel_unregister()
