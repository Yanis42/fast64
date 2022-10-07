import bpy
from bpy.utils import register_class, unregister_class

from ..utility import prop_split, gammaInverse
from .oot_collision import OOTWaterBoxProperty, drawWaterBoxProperty
from .oot_constants import ootRegisterQueue, ootEnumEmptyType
from .actor.classes import OOTActorProperty, OOTTransitionActorProperty, OOTEntranceProperty
from .oot_utility import getSceneObj, getRoomObj
from .scene.operators import OOT_SearchSceneEnumOperator, OOT_SearchMusicSeqEnumOperator
from .scene.classes import OOTSceneProperties, OOTSceneHeaderProperty, OOTAlternateSceneHeaderProperty
from .scene.draw import drawSceneHeaderProperty, drawAlternateSceneHeaderProperty
from .room.operators import OOT_SearchObjectEnumOperator
from .room.classes import OOTRoomHeaderProperty, OOTAlternateRoomHeaderProperty
from .room.draw import drawRoomHeaderProperty, drawAlternateRoomHeaderProperty
from .cutscene.draw import drawCutsceneProperty

from .actor.draw import (
    drawActorProperty,
    drawTransitionActorProperty,
    drawEntranceProperty,
    drawActorHeaderProperty
)

from .cutscene.classes import (
    OOTCutsceneProperty,
    OOTCSTextboxProperty,
    OOTCSLightingProperty,
    OOTCSTimeProperty,
    OOTCSBGMProperty,
    OOTCSMiscProperty,
    OOTCS0x09Property,
    OOTCSUnkProperty,
    OOTCSListProperty,
)
from .cutscene.operators import (
    OOTCSTextboxAdd,
    OOTCSListAdd,
)

def headerSettingsToIndices(headerSettings):
    headers = set()
    if headerSettings.childDayHeader:
        headers.add(0)
    if headerSettings.childNightHeader:
        headers.add(1)
    if headerSettings.adultDayHeader:
        headers.add(2)
    if headerSettings.adultNightHeader:
        headers.add(3)
    for cutsceneHeader in headerSettings.cutsceneHeaders:
        headers.add(cutsceneHeader.headerIndex)

    return headers


class OOTObjectPanel(bpy.types.Panel):
    bl_label = "Object Inspector"
    bl_idname = "OBJECT_PT_OOT_Object_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "OOT" and (context.object is not None and context.object.data is None)

    def draw(self, context):
        prop_split(self.layout, context.scene, "gameEditorMode", "Game")
        box = self.layout.box()
        box.box().label(text="OOT Object Inspector")
        obj = context.object
        objName = obj.name
        prop_split(box, obj, "ootEmptyType", "Object Type")

        sceneObj = getSceneObj(obj)
        roomObj = getRoomObj(obj)

        altSceneProp = sceneObj.ootAlternateSceneHeaders if sceneObj is not None else None
        altRoomProp = roomObj.ootAlternateRoomHeaders if roomObj is not None else None

        if obj.ootEmptyType == "Actor":
            actorProp = obj.ootActorProperty
            drawActorProperty(box, actorProp, objName)
            drawActorHeaderProperty(box.column(), actorProp.headerSettings, "Actor", altRoomProp, objName)

        elif obj.ootEmptyType == "Transition Actor":
            transLayout = box.column()
            if roomObj is None:
                transLayout.label(text="This must be part of a Room empty's hierarchy.", icon="OUTLINER")
            else:
                transActorProp = obj.ootTransitionActorProperty
                drawTransitionActorProperty(transLayout, transActorProp, roomObj.ootRoomHeader.roomIndex, objName)
                drawActorHeaderProperty(
                    transLayout, transActorProp.actor.headerSettings, "Transition Actor", altSceneProp, objName
                )

        elif obj.ootEmptyType == "Water Box":
            wBoxLayout = box.column()
            if roomObj is None:
                wBoxLayout.label(text="This must be part of a Room empty's hierarchy.", icon="OUTLINER")
            drawWaterBoxProperty(box, obj.ootWaterBoxProperty, roomObj.ootRoomHeader.roomIndex)

        elif obj.ootEmptyType == "Scene":
            menuTab = obj.ootSceneHeader.menuTab
            drawSceneHeaderProperty(box, obj.ootSceneHeader, None, None, objName)
            if menuTab == "Alternate":
                drawAlternateSceneHeaderProperty(box, obj.ootAlternateSceneHeaders, objName)
            elif menuTab == "General":
                box.box().label(text="Write Dummy Room List")
                box.label(text="Use ``NULL`` for room seg start/end offsets")
                box.prop(obj.fast64.oot.scene, "write_dummy_room_list")

        elif obj.ootEmptyType == "Room":
            drawRoomHeaderProperty(box, obj.ootRoomHeader, None, None, objName)
            if obj.ootRoomHeader.menuTab == "Alternate":
                drawAlternateRoomHeaderProperty(box, obj.ootAlternateRoomHeaders, objName)

        elif obj.ootEmptyType == "Entrance":
            entranceLayout = box.column()
            if roomObj is None:
                entranceLayout.label(text="This must be part of a Room empty's hierarchy.", icon="OUTLINER")
            else:
                split = entranceLayout.split(factor=0.5)
                split.label(text=f"Room Index: {roomObj.ootRoomHeader.roomIndex}")
                entranceProp = obj.ootEntranceProperty
                drawEntranceProperty(entranceLayout, entranceProp)
                drawActorHeaderProperty(
                    entranceLayout, entranceProp.actor.headerSettings, "Entrance", altSceneProp, objName
                )

        elif obj.ootEmptyType == "Cull Group":
            drawCullGroupProperty(box, obj)

        elif obj.ootEmptyType == "LOD":
            drawLODProperty(box, obj)

        elif obj.ootEmptyType == "Cutscene":
            drawCutsceneProperty(box, obj)

        elif obj.ootEmptyType == "None":
            box.label(text="Geometry can be parented to this.")


def drawLODProperty(box, obj):
    col = box.column()
    col.box().label(text="LOD Settings (Blender Units)")
    for otherObj in obj.children:
        if bpy.context.scene.exportHiddenGeometry or not otherObj.hide_get():
            prop_split(col, otherObj, "f3d_lod_z", otherObj.name)
    col.prop(obj, "f3d_lod_always_render_farthest")


def drawCullGroupProperty(box, obj):
    col = box.column()
    col.label(text="Use Options -> Transform -> Affect Only -> Parent ")
    col.label(text="to move object without affecting children.")


def setLightPropertyValues(lightProp, ambient, diffuse0, diffuse1, fogColor, fogNear):
    lightProp.ambient = gammaInverse([value / 255 for value in ambient]) + [1]
    lightProp.diffuse0 = gammaInverse([value / 255 for value in diffuse0]) + [1]
    lightProp.diffuse1 = gammaInverse([value / 255 for value in diffuse1]) + [1]
    lightProp.fogColor = gammaInverse([value / 255 for value in fogColor]) + [1]
    lightProp.fogNear = fogNear


def onUpdateOOTEmptyType(self, context):
    isNoneEmpty = self.ootEmptyType == "None"
    isBoxEmpty = self.ootEmptyType == "Water Box"
    isSphereEmpty = self.ootEmptyType == "Cull Group"
    self.show_name = not (isBoxEmpty or isNoneEmpty or isSphereEmpty)
    self.show_axis = not (isBoxEmpty or isNoneEmpty or isSphereEmpty)

    if isBoxEmpty:
        self.empty_display_type = "CUBE"

    if isSphereEmpty:
        self.empty_display_type = "SPHERE"

    if self.ootEmptyType == "Scene":
        if len(self.ootSceneHeader.lightList) == 0:
            light = self.ootSceneHeader.lightList.add()
        if not self.ootSceneHeader.timeOfDayLights.defaultsSet:
            self.ootSceneHeader.timeOfDayLights.defaultsSet = True
            timeOfDayLights = self.ootSceneHeader.timeOfDayLights
            setLightPropertyValues(
                timeOfDayLights.dawn, [70, 45, 57], [180, 154, 138], [20, 20, 60], [140, 120, 100], 0x3E1
            )
            setLightPropertyValues(
                timeOfDayLights.day, [105, 90, 90], [255, 255, 240], [50, 50, 90], [100, 100, 120], 0x3E4
            )
            setLightPropertyValues(
                timeOfDayLights.dusk, [120, 90, 0], [250, 135, 50], [30, 30, 60], [120, 70, 50], 0x3E3
            )
            setLightPropertyValues(timeOfDayLights.night, [40, 70, 100], [20, 20, 35], [50, 50, 100], [0, 0, 30], 0x3E0)


class OOT_ObjectProperties(bpy.types.PropertyGroup):
    version: bpy.props.IntProperty(name="OOT_ObjectProperties Version", default=0)
    cur_version = 0  # version after property migration

    scene: bpy.props.PointerProperty(type=OOTSceneProperties)


oot_obj_classes = [
    OOTSceneProperties,
    OOT_ObjectProperties,
    OOT_SearchMusicSeqEnumOperator,
    OOT_SearchObjectEnumOperator,
    OOT_SearchSceneEnumOperator,
    OOTCSTextboxProperty,
    OOTCSTextboxAdd,
    OOTCSLightingProperty,
    OOTCSTimeProperty,
    OOTCSBGMProperty,
    OOTCSMiscProperty,
    OOTCS0x09Property,
    OOTCSUnkProperty,
    OOTCSListProperty,
    OOTCSListAdd,
    OOTCutsceneProperty,
]

oot_obj_panel_classes = (OOTObjectPanel,)


def oot_obj_panel_register():
    for cls in oot_obj_panel_classes:
        register_class(cls)


def oot_obj_panel_unregister():
    for cls in oot_obj_panel_classes:
        unregister_class(cls)


def oot_obj_register():
    oot_obj_classes.extend(ootRegisterQueue)

    for cls in oot_obj_classes:
        register_class(cls)

    bpy.types.Object.ootEmptyType = bpy.props.EnumProperty(
        name="OOT Object Type", items=ootEnumEmptyType, default="None", update=onUpdateOOTEmptyType
    )

    bpy.types.Object.ootActorProperty = bpy.props.PointerProperty(type=OOTActorProperty)
    bpy.types.Object.ootTransitionActorProperty = bpy.props.PointerProperty(type=OOTTransitionActorProperty)
    bpy.types.Object.ootWaterBoxProperty = bpy.props.PointerProperty(type=OOTWaterBoxProperty)
    bpy.types.Object.ootRoomHeader = bpy.props.PointerProperty(type=OOTRoomHeaderProperty)
    bpy.types.Object.ootSceneHeader = bpy.props.PointerProperty(type=OOTSceneHeaderProperty)
    bpy.types.Object.ootAlternateSceneHeaders = bpy.props.PointerProperty(type=OOTAlternateSceneHeaderProperty)
    bpy.types.Object.ootAlternateRoomHeaders = bpy.props.PointerProperty(type=OOTAlternateRoomHeaderProperty)
    bpy.types.Object.ootEntranceProperty = bpy.props.PointerProperty(type=OOTEntranceProperty)
    bpy.types.Object.ootCutsceneProperty = bpy.props.PointerProperty(type=OOTCutsceneProperty)


def oot_obj_unregister():

    del bpy.types.Object.ootEmptyType

    del bpy.types.Object.ootActorProperty
    del bpy.types.Object.ootTransitionActorProperty
    del bpy.types.Object.ootWaterBoxProperty
    del bpy.types.Object.ootRoomHeader
    del bpy.types.Object.ootSceneHeader
    del bpy.types.Object.ootAlternateSceneHeaders
    del bpy.types.Object.ootAlternateRoomHeaders
    del bpy.types.Object.ootEntranceProperty
    del bpy.types.Object.ootCutsceneProperty

    for cls in reversed(oot_obj_classes):
        unregister_class(cls)
