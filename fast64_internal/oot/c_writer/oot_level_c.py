from ...utility import CData, PluginError
from ...f3d.f3d_gbi import ScrollMethod

from ..oot_model_classes import OOTGfxFormatter
from ..oot_level_classes import OOTScene, OOTRoom
from ..oot_constants import ootRoomShapeStructs, ootRoomShapeEntryStructs
from ..oot_utility import indent
from ..oot_collision import ootCollisionToC
from ..oot_cutscene import ootCutsceneDataToC

from .oot_scene_room_cmds.oot_scene_room_cmds import (
    getRoomCommandsList,
    getSceneCommandsList,
)


def ootObjectListToC(room, headerIndex):
    data = CData()
    data.header = "extern s16 " + room.objectListName(headerIndex) + "[" + str(len(room.objectIDList)) + "];\n"
    data.source = "s16 " + room.objectListName(headerIndex) + "[" + str(len(room.objectIDList)) + "] = {\n"
    for objectItem in room.objectIDList:
        data.source += "\t" + objectItem + ",\n"
    data.source += "};\n\n"
    return data


def ootActorToC(actor):
    return (
        "{ "
        + ", ".join(
            (
                str(actor.actorID),
                str(int(round(actor.position[0]))),
                str(int(round(actor.position[1]))),
                str(int(round(actor.position[2]))),
                *(
                    (
                        actor.rotOverride[0],
                        actor.rotOverride[1],
                        actor.rotOverride[2],
                    )
                    if actor.rotOverride is not None
                    else (
                        str(int(round(actor.rotation[0]))),
                        str(int(round(actor.rotation[1]))),
                        str(int(round(actor.rotation[2]))),
                    )
                ),
                str(actor.actorParam),
            )
        )
        + " },\n"
    )


def ootActorListToC(room, headerIndex):
    data = CData()
    data.header = "extern ActorEntry " + room.actorListName(headerIndex) + "[" + str(len(room.actorIDList)) + "];\n"
    data.source = "ActorEntry " + room.actorListName(headerIndex) + "[" + str(len(room.actorIDList)) + "] = {\n"
    for actor in room.actorIDList:
        data.source += "\t" + ootActorToC(actor)
    data.source += "};\n\n"
    return data


def ootMeshEntryToC(meshEntry, roomShape):
    opaqueName = meshEntry.DLGroup.opaque.name if meshEntry.DLGroup.opaque is not None else "0"
    transparentName = meshEntry.DLGroup.transparent.name if meshEntry.DLGroup.transparent is not None else "0"
    data = "{ "
    if roomShape == "ROOM_SHAPE_TYPE_IMAGE":
        raise PluginError("Pre-Rendered rooms not supported.")
    elif roomShape == "ROOM_SHAPE_TYPE_CULLABLE":
        data += (
            "{ "
            + f"{meshEntry.cullGroup.position[0]}, {meshEntry.cullGroup.position[1]}, {meshEntry.cullGroup.position[2]}"
            + " }, "
        )
        data += str(meshEntry.cullGroup.cullDepth) + ", "
    data += (
        (opaqueName if opaqueName != "0" else "NULL")
        + ", "
        + (transparentName if transparentName != "0" else "NULL")
        + " },\n"
    )

    return data


def ootRoomMeshToC(room, textureExportSettings):
    mesh = room.mesh
    if len(mesh.meshEntries) == 0:
        raise PluginError("Error: Room " + str(room.index) + " has no mesh children.")

    meshHeader = CData()
    meshHeader.header = f"extern {ootRoomShapeStructs[mesh.roomShape]} {mesh.headerName()};\n"
    meshHeader.source = (
        "\n".join(
            (
                ootRoomShapeStructs[mesh.roomShape] + " " + mesh.headerName() + " = {",
                indent + mesh.roomShape + ",",
                indent + "ARRAY_COUNT(" + mesh.entriesName() + ")" + ",",
                indent + mesh.entriesName() + ",",
                indent + mesh.entriesName() + " + ARRAY_COUNT(" + mesh.entriesName() + ")",
                "};",
            )
        )
        + "\n\n"
    )

    meshEntries = CData()
    meshEntries.header = (
        f"extern {ootRoomShapeEntryStructs[mesh.roomShape]} {mesh.entriesName()}[{str(len(mesh.meshEntries))}];\n"
    )
    meshEntries.source = (
        f"{ootRoomShapeEntryStructs[mesh.roomShape]} {mesh.entriesName()}[{str(len(mesh.meshEntries))}] = " + "{\n"
    )
    meshData = CData()
    for entry in mesh.meshEntries:
        meshEntries.source += "\t" + ootMeshEntryToC(entry, mesh.roomShape)
        if entry.DLGroup.opaque is not None:
            meshData.append(entry.DLGroup.opaque.to_c(mesh.model.f3d))
        if entry.DLGroup.transparent is not None:
            meshData.append(entry.DLGroup.transparent.to_c(mesh.model.f3d))
    meshEntries.source += "};\n\n"
    exportData = mesh.model.to_c(textureExportSettings, OOTGfxFormatter(ScrollMethod.Vertex))

    meshData.append(exportData.all())
    meshHeader.append(meshEntries)

    return meshHeader, meshData


def ootRoomCommandsToC(room: OOTRoom, headerIndex: int):
    roomCmdList = getRoomCommandsList(room, headerIndex)
    roomCmdData = CData()

    roomCmdData.header = f"extern SCmdBase {room.roomHeaderName(headerIndex)}[];\n"
    roomCmdData.source = (
        f"SCmdBase {room.roomHeaderName(headerIndex)}[]"
        + " = {\n"
        + "".join([roomCmd.source for roomCmd in roomCmdList])
        + "};\n\n"
    )

    return roomCmdData


def ootAlternateRoomMainToC(scene, room):
    altHeader = CData()
    altData = CData()

    altHeader.header = "extern SCmdBase* " + room.alternateHeadersName() + "[];\n"
    altHeader.source = "SCmdBase* " + room.alternateHeadersName() + "[] = {\n"

    if room.childNightHeader is not None:
        altHeader.source += "\t" + room.roomName() + "_header" + format(1, "02") + ",\n"
        altData.append(ootRoomMainToC(scene, room.childNightHeader, 1))
    else:
        altHeader.source += "\t0,\n"

    if room.adultDayHeader is not None:
        altHeader.source += "\t" + room.roomName() + "_header" + format(2, "02") + ",\n"
        altData.append(ootRoomMainToC(scene, room.adultDayHeader, 2))
    else:
        altHeader.source += "\t0,\n"

    if room.adultNightHeader is not None:
        altHeader.source += "\t" + room.roomName() + "_header" + format(3, "02") + ",\n"
        altData.append(ootRoomMainToC(scene, room.adultNightHeader, 3))
    else:
        altHeader.source += "\t0,\n"

    for i in range(len(room.cutsceneHeaders)):
        altHeader.source += "\t" + room.roomName() + "_header" + format(i + 4, "02") + ",\n"
        altData.append(ootRoomMainToC(scene, room.cutsceneHeaders[i], i + 4))

    altHeader.source += "};\n\n"

    return altHeader, altData


def ootRoomMainToC(scene, room, headerIndex):
    roomMainC = CData()

    if room.hasAlternateHeaders():
        altHeader, altData = ootAlternateRoomMainToC(scene, room)
    else:
        altHeader = CData()
        altData = CData()

    roomMainC.append(ootRoomCommandsToC(room, headerIndex))
    roomMainC.append(altHeader)
    if len(room.objectIDList) > 0:
        roomMainC.append(ootObjectListToC(room, headerIndex))
    if len(room.actorIDList) > 0:
        roomMainC.append(ootActorListToC(room, headerIndex))
    roomMainC.append(altData)

    return roomMainC


def ootSceneCommandsToC(scene: OOTScene, headerIndex: int):
    """
    Converts every scene commands to C code.
    Contains scene command defines (examples: ``SCENE_CMD_ROOM_LIST``, ``SCENE_CMD_CUTSCENE_DATA``)
    """
    sceneCmdList = getSceneCommandsList(scene, headerIndex)

    # add the commands to the file data
    sceneCmdData = CData()
    sceneCmdData.header = f"extern SCmdBase {scene.sceneHeaderName(headerIndex)}[];\n"
    sceneCmdData.source = (
        f"SCmdBase {scene.sceneHeaderName(headerIndex)}[]"
        + " = {\n"
        + "".join([sceneCmd.source for sceneCmd in sceneCmdList])
        + "};\n\n"
    )

    return sceneCmdData


def ootStartPositionListToC(scene, headerIndex):
    data = CData()
    data.header = "extern ActorEntry " + scene.startPositionsName(headerIndex) + "[];\n"
    data.source = "ActorEntry " + scene.startPositionsName(headerIndex) + "[] = {\n"
    for i in range(len(scene.startPositions)):
        data.source += "\t" + ootActorToC(scene.startPositions[i])
    data.source += "};\n\n"
    return data


def ootTransitionActorToC(transActor):
    return (
        "{ "
        + ", ".join(
            (
                str(transActor.frontRoom),
                str(transActor.frontCam),
                str(transActor.backRoom),
                str(transActor.backCam),
                str(transActor.actorID),
                str(int(round(transActor.position[0]))),
                str(int(round(transActor.position[1]))),
                str(int(round(transActor.position[2]))),
                str(int(round(transActor.rotationY))),
                str(transActor.actorParam),
            )
        )
        + " },\n"
    )


def ootTransitionActorListToC(scene, headerIndex):
    data = CData()
    data.header = (
        "extern TransitionActorEntry "
        + scene.transitionActorListName(headerIndex)
        + "["
        + str(len(scene.transitionActorList))
        + "];\n"
    )
    data.source = (
        "TransitionActorEntry "
        + scene.transitionActorListName(headerIndex)
        + "["
        + str(len(scene.transitionActorList))
        + "] = {\n"
    )
    for transActor in scene.transitionActorList:
        data.source += "\t" + ootTransitionActorToC(transActor)
    data.source += "};\n\n"
    return data


def ootRoomExternToC(room):
    return ("extern u8 _" + room.roomName() + "SegmentRomStart[];\n") + (
        "extern u8 _" + room.roomName() + "SegmentRomEnd[];\n"
    )


def ootRoomListEntryToC(room):
    return "{ (u32)_" + room.roomName() + "SegmentRomStart, (u32)_" + room.roomName() + "SegmentRomEnd },\n"


def ootRoomListHeaderToC(scene):
    data = CData()

    data.header += "extern RomFile " + scene.roomListName() + "[];\n"

    if scene.write_dummy_room_list:
        data.source += "// Dummy room list\n"
        data.source += "RomFile " + scene.roomListName() + "[] = {\n"
        data.source += "\t{0, 0},\n" * len(scene.rooms)
        data.source += "};\n\n"
    else:
        # Write externs for rom segments
        for i in range(len(scene.rooms)):
            data.source += ootRoomExternToC(scene.rooms[i])
        data.source += "\n"

        data.source += "RomFile " + scene.roomListName() + "[] = {\n"

        for i in range(len(scene.rooms)):
            data.source += "\t" + ootRoomListEntryToC(scene.rooms[i])
        data.source += "};\n\n"

    return data


def ootEntranceToC(entrance):
    return "{ " + str(entrance.startPositionIndex) + ", " + str(entrance.roomIndex) + " },\n"


def ootEntranceListToC(scene, headerIndex):
    data = CData()
    data.header = "extern EntranceEntry " + scene.entranceListName(headerIndex) + "[];\n"
    data.source = "EntranceEntry " + scene.entranceListName(headerIndex) + "[] = {\n"
    for entrance in scene.entranceList:
        data.source += "\t" + ootEntranceToC(entrance)
    data.source += "};\n\n"
    return data


def ootExitListToC(scene, headerIndex):
    data = CData()
    data.header = "extern u16 " + scene.exitListName(headerIndex) + "[" + str(len(scene.exitList)) + "];\n"
    data.source = "u16 " + scene.exitListName(headerIndex) + "[" + str(len(scene.exitList)) + "] = {\n"
    for exitEntry in scene.exitList:
        data.source += "\t" + str(exitEntry.index) + ",\n"
    data.source += "};\n\n"
    return data


def ootVectorToC(vector):
    return "0x{:02X}, 0x{:02X}, 0x{:02X}".format(vector[0], vector[1], vector[2])


def ootLightToC(light):
    return (
        "\t{ "
        + ", ".join(
            (
                ootVectorToC(light.ambient),
                ootVectorToC(light.diffuseDir0),
                ootVectorToC(light.diffuse0),
                ootVectorToC(light.diffuseDir1),
                ootVectorToC(light.diffuse1),
                ootVectorToC(light.fogColor),
                light.getBlendFogShort(),
                "0x{:04X}".format(light.fogFar),
            )
        )
        + " },\n"
    )


def ootLightSettingsToC(scene, useIndoorLighting, headerIndex):
    data = CData()
    lightArraySize = len(scene.lights)
    data.header = "extern LightSettings " + scene.lightListName(headerIndex) + "[" + str(lightArraySize) + "];\n"
    data.source = "LightSettings " + scene.lightListName(headerIndex) + "[" + str(lightArraySize) + "] = {\n"
    for light in scene.lights:
        data.source += ootLightToC(light)
    data.source += "};\n\n"
    return data


def ootPathToC(path):
    data = CData()
    data.header = "extern Vec3s " + path.pathName() + "[];\n"
    data.source = "Vec3s " + path.pathName() + "[] = {\n"
    for point in path.points:
        data.source += (
            "\t"
            + "{ "
            + str(int(round(point[0])))
            + ", "
            + str(int(round(point[1])))
            + ", "
            + str(int(round(point[2])))
            + " },\n"
        )
    data.source += "};\n\n"

    return data


def ootPathListToC(scene):
    data = CData()
    data.header = "extern Path " + scene.pathListName() + "[" + str(len(scene.pathList)) + "];\n"
    data.source = "Path " + scene.pathListName() + "[" + str(len(scene.pathList)) + "] = {\n"
    pathData = CData()
    for i in range(len(scene.pathList)):
        path = scene.pathList[i]
        data.source += "\t" + "{ " + str(len(path.points)) + ", " + path.pathName() + " },\n"
        pathData.append(ootPathToC(path))
    data.source += "};\n\n"
    pathData.append(data)
    return pathData


def ootSceneMeshToC(scene, textureExportSettings):
    exportData = scene.model.to_c(textureExportSettings, OOTGfxFormatter(ScrollMethod.Vertex))
    return exportData.all()


def ootSceneIncludes(scene):
    data = CData()
    data.source += '#include "ultra64.h"\n'
    data.source += '#include "z64.h"\n'
    data.source += '#include "macros.h"\n'
    data.source += '#include "' + scene.sceneName() + '.h"\n\n'
    data.source += '#include "segment_symbols.h"\n'
    data.source += '#include "command_macros_base.h"\n'
    data.source += '#include "z64cutscene_commands.h"\n'
    data.source += '#include "variables.h"\n'
    data.source += "\n"
    return data


def ootAlternateSceneMainToC(scene):
    altHeader = CData()
    altData = CData()

    altHeader.header = "extern SCmdBase* " + scene.alternateHeadersName() + "[];\n"
    altHeader.source = "SCmdBase* " + scene.alternateHeadersName() + "[] = {\n"

    if scene.childNightHeader is not None:
        altHeader.source += "\t" + scene.sceneName() + "_header" + format(1, "02") + ",\n"
        altData.append(ootSceneMainToC(scene.childNightHeader, 1))
    else:
        altHeader.source += "\t0,\n"

    if scene.adultDayHeader is not None:
        altHeader.source += "\t" + scene.sceneName() + "_header" + format(2, "02") + ",\n"
        altData.append(ootSceneMainToC(scene.adultDayHeader, 2))
    else:
        altHeader.source += "\t0,\n"

    if scene.adultNightHeader is not None:
        altHeader.source += "\t" + scene.sceneName() + "_header" + format(3, "02") + ",\n"
        altData.append(ootSceneMainToC(scene.adultNightHeader, 3))
    else:
        altHeader.source += "\t0,\n"

    for i in range(len(scene.cutsceneHeaders)):
        altHeader.source += "\t" + scene.sceneName() + "_header" + format(i + 4, "02") + ",\n"
        altData.append(ootSceneMainToC(scene.cutsceneHeaders[i], i + 4))

    altHeader.source += "};\n\n"

    return altHeader, altData


def ootSceneMainToC(scene, headerIndex):
    sceneMainC = CData()

    if headerIndex == 0:
        # Check if this is the first time the function is being called, we do not want to write this data multiple times
        roomHeaderData = ootRoomListHeaderToC(scene)
        if len(scene.pathList) > 0:
            pathData = ootPathListToC(scene)
        else:
            pathData = CData()
    else:
        # The function has already been called (and is being called for another scene header), so we can make this data be a blank string
        roomHeaderData = CData()
        pathData = CData()

    if scene.hasAlternateHeaders():
        # Gets the alternate data for the scene's main c file
        altHeader, altData = ootAlternateSceneMainToC(scene)
    else:
        # Since the scene does not use alternate headers, this data can just be a blank string
        altHeader = CData()
        altData = CData()

    # Write the scene header
    sceneMainC.append(ootSceneCommandsToC(scene, headerIndex))

    # Write alternate scene headers
    sceneMainC.append(altHeader)

    # Write the spawn position list data
    if len(scene.startPositions) > 0:
        sceneMainC.append(ootStartPositionListToC(scene, headerIndex))

    # Write the transition actor list data
    if len(scene.transitionActorList) > 0:
        sceneMainC.append(ootTransitionActorListToC(scene, headerIndex))

    # Write the room segment list
    sceneMainC.append(roomHeaderData)

    # Write the entrance list
    if len(scene.entranceList) > 0:
        sceneMainC.append(ootEntranceListToC(scene, headerIndex))

    # Write the exit list
    if len(scene.exitList) > 0:
        sceneMainC.append(ootExitListToC(scene, headerIndex))

    # Write the light data
    if len(scene.lights) > 0:
        sceneMainC.append(ootLightSettingsToC(scene, scene.skyboxLighting == "0x01", headerIndex))

    # Write the path data, if used
    sceneMainC.append(pathData)

    # Write the data from alternate headers
    sceneMainC.append(altData)

    return sceneMainC


# Writes the textures and material setup displaylists that are shared between multiple rooms (is written to the scene)
def ootSceneTexturesToC(scene, textureExportSettings):
    sceneTextures = CData()
    sceneTextures.append(ootSceneMeshToC(scene, textureExportSettings))
    return sceneTextures


# Writes the collision data for a scene
def ootSceneCollisionToC(scene):
    sceneCollisionC = CData()
    sceneCollisionC.append(ootCollisionToC(scene.collision))
    return sceneCollisionC


# scene is either None or an OOTScene. This can either be the main scene itself,
# or one of the alternate / cutscene headers.
def ootGetCutsceneC(scene, headerIndex):
    if scene is not None and scene.writeCutscene:
        if scene.csWriteType == "Embedded":
            return [ootCutsceneDataToC(scene, scene.cutsceneDataName(headerIndex))]
        elif scene.csWriteType == "Object":
            return [ootCutsceneDataToC(scene.csWriteObject, scene.csWriteObject.name)]
    return []


def ootSceneCutscenesToC(scene):
    sceneCutscenes = ootGetCutsceneC(scene, 0)
    sceneCutscenes.extend(ootGetCutsceneC(scene.childNightHeader, 1))
    sceneCutscenes.extend(ootGetCutsceneC(scene.adultDayHeader, 2))
    sceneCutscenes.extend(ootGetCutsceneC(scene.adultNightHeader, 3))

    for i in range(len(scene.cutsceneHeaders)):
        sceneCutscenes.extend(ootGetCutsceneC(scene.cutsceneHeaders[i], i + 4))
    for ec in scene.extraCutscenes:
        sceneCutscenes.append(ootCutsceneDataToC(ec, ec.name))

    return sceneCutscenes


def ootLevelToC(scene, textureExportSettings):
    levelC = OOTLevelC()

    levelC.sceneMainC = ootSceneMainToC(scene, 0)
    levelC.sceneTexturesC = ootSceneTexturesToC(scene, textureExportSettings)
    levelC.sceneCollisionC = ootSceneCollisionToC(scene)
    levelC.sceneCutscenesC = ootSceneCutscenesToC(scene)

    for i in range(len(scene.rooms)):
        levelC.roomMainC[scene.rooms[i].roomName()] = ootRoomMainToC(scene, scene.rooms[i], 0)
        meshHeader, meshData = ootRoomMeshToC(scene.rooms[i], textureExportSettings)
        levelC.roomMeshInfoC[scene.rooms[i].roomName()] = meshHeader
        levelC.roomMeshC[scene.rooms[i].roomName()] = meshData
    return levelC


class OOTLevelC:
    def sceneTexturesIsUsed(self):
        return len(self.sceneTexturesC.source) > 0

    def sceneCutscenesIsUsed(self):
        return len(self.sceneCutscenesC) > 0

    def __init__(self):
        # Main header file for both the scene and room(s)
        self.header = CData()
        # Files for the scene segment
        self.sceneMainC = CData()
        self.sceneTexturesC = CData()
        self.sceneCollisionC = CData()
        self.sceneCutscenesC = []
        # Files for room segments
        self.roomMainC = {}
        self.roomMeshInfoC = {}
        self.roomMeshC = {}
