import bpy
import os

from dataclasses import dataclass, field
from mathutils import Matrix
from bpy.types import Object
from ...f3d.f3d_gbi import DLFormat, TextureExportSettings
from ..scene.properties import OOTBootupSceneOptions, OOTSceneHeaderProperty
from ..scene.exporter.to_c import setBootupScene
from ..room.properties import OOTRoomHeaderProperty
from ..oot_constants import ootData
from ..oot_object import addMissingObjectsToAllRoomHeadersNew
from ..oot_model_classes import OOTModel
from ..oot_f3d_writer import writeTextureArraysNew
from ..oot_level_writer import BoundingBox, writeTextureArraysExistingScene, ootProcessMesh
from ..oot_utility import CullGroup
from .common import Common, altHeaderList, includeData
from .scene import OOTScene
from .scene_header import OOTSceneAlternateHeader
from .room import OOTRoom, OOTRoomAlternateHeader
from .file import Files

from ...utility import (
    PluginError,
    checkObjectReference,
    unhideAllAndGetHiddenState,
    restoreHiddenState,
    toAlnum,
    writeFile,
)

from ..oot_utility import (
    ExportInfo,
    OOTObjectCategorizer,
    ootDuplicateHierarchy,
    ootCleanupScene,
    getSceneDirFromLevelName,
    ootGetPath,
)


@dataclass
class OOTRoomData:
    """This class hosts the C data for every room files"""

    name: str
    roomMain: str = None
    roomModel: str = None
    roomModelInfo: str = None


@dataclass
class OOTSceneData:
    """This class hosts the C data for every scene files"""

    sceneMain: str = None
    sceneCollision: str = None
    sceneCutscenes: list[str] = field(default_factory=list)
    sceneTextures: str = None


@dataclass
class OOTSceneExport:
    """This class is the main exporter class, it handles generating the C data and writing the files"""

    exportInfo: ExportInfo
    originalSceneObj: Object
    sceneName: str
    ootBlenderScale: float
    transform: Matrix
    f3dType: str
    saveTexturesAsPNG: bool
    hackerootBootOption: OOTBootupSceneOptions
    singleFileExport: bool
    isHWv1: bool
    textureExportSettings: TextureExportSettings
    dlFormat: DLFormat = DLFormat.Static

    sceneObj: Object = None
    scene: OOTScene = None
    path: str = None
    sceneBasePath: str = None
    header: str = ""
    sceneData: OOTSceneData = None
    roomList: dict[int, OOTRoomData] = field(default_factory=dict)
    hasCutscenes: bool = False
    hasSceneTextures: bool = False

    def __post_init__(self):
        self.header = (
            f"#ifndef {self.sceneName.upper()}_SCENE_H\n"
            + f"#define {self.sceneName.upper()}_SCENE_H\n\n"
        )

    def getNewRoomList(self, scene: OOTScene):
        """Returns the room list from empty objects with the type 'Room'"""

        roomDict: dict[int, OOTRoom] = {}
        roomObjs: list[Object] = [
            obj for obj in self.sceneObj.children_recursive if obj.type == "EMPTY" and obj.ootEmptyType == "Room"
        ]

        if len(roomObjs) == 0:
            raise PluginError("ERROR: The scene has no child empties with the 'Room' empty type.")

        for roomObj in roomObjs:
            altProp = roomObj.ootAlternateRoomHeaders
            roomHeader = roomObj.ootRoomHeader
            roomIndex = roomHeader.roomIndex

            if roomIndex in roomDict:
                raise PluginError(f"ERROR: Room index {roomIndex} used more than once!")

            roomName = f"{toAlnum(self.sceneName)}_room_{roomIndex}"
            roomDict[roomIndex] = OOTRoom(
                self.sceneObj,
                self.transform,
                roomIndex,
                roomName,
                roomObj,
                roomHeader.roomShape,
                scene.model.addSubModel(
                    OOTModel(
                        scene.model.f3d.F3D_VER,
                        scene.model.f3d._HW_VERSION_1,
                        roomName + "_dl",
                        scene.model.DLFormat,
                        None,
                    )
                ),
            )

            # Mesh stuff
            c = Common(self.sceneObj, self.transform)
            pos, _, scale, _ = c.getConvertedTransform(self.transform, self.sceneObj, roomObj, True)
            cullGroup = CullGroup(pos, scale, roomObj.ootRoomHeader.defaultCullDistance)
            DLGroup = roomDict[roomIndex].mesh.addMeshGroup(cullGroup).DLGroup
            boundingBox = BoundingBox()
            ootProcessMesh(
                roomDict[roomIndex].mesh,
                DLGroup,
                self.sceneObj,
                roomObj,
                self.transform,
                not self.saveTexturesAsPNG,
                None,
                boundingBox,
            )

            centroid, radius = boundingBox.getEnclosingSphere()
            cullGroup.position = centroid
            cullGroup.cullDepth = radius

            roomDict[roomIndex].mesh.terminateDLs()
            roomDict[roomIndex].mesh.removeUnusedEntries()

            # Other
            if roomHeader.roomShape == "ROOM_SHAPE_TYPE_IMAGE" and len(roomHeader.bgImageList) < 1:
                raise PluginError(f'Room {roomObj.name} uses room shape "Image" but doesn\'t have any BG images.')

            if roomHeader.roomShape == "ROOM_SHAPE_TYPE_IMAGE" and len(roomDict) > 1:
                raise PluginError(f'Room shape "Image" can only have one room in the scene.')

            roomDict[roomIndex].roomShape = roomDict[roomIndex].getNewRoomShape(roomHeader, self.sceneName)
            altHeaderData = OOTRoomAlternateHeader(f"{roomDict[roomIndex].name}_alternateHeaders")
            roomDict[roomIndex].mainHeader = roomDict[roomIndex].getNewRoomHeader(roomHeader)
            hasAltHeader = False

            for i, header in enumerate(altHeaderList, 1):
                altP: OOTRoomHeaderProperty = getattr(altProp, f"{header}Header")
                if not altP.usePreviousHeader:
                    hasAltHeader = True
                    setattr(altHeaderData, header, roomDict[roomIndex].getNewRoomHeader(altP, i))

            altHeaderData.cutscenes = [
                roomDict[roomIndex].getNewRoomHeader(csHeader, i)
                for i, csHeader in enumerate(altProp.cutsceneHeaders, 4)
            ]

            if len(altHeaderData.cutscenes) > 0:
                hasAltHeader = True

            roomDict[roomIndex].altHeader = altHeaderData if hasAltHeader else None
            addMissingObjectsToAllRoomHeadersNew(roomObj, roomDict[roomIndex], ootData)

        return [roomDict[i] for i in range(min(roomDict.keys()), len(roomDict))]

    def getNewScene(self):
        """Returns and creates scene data"""
        # init
        if self.originalSceneObj.type != "EMPTY" or self.originalSceneObj.ootEmptyType != "Scene":
            raise PluginError(f'{self.originalSceneObj.name} is not an empty with the "Scene" empty type.')

        if bpy.context.scene.exportHiddenGeometry:
            hiddenState = unhideAllAndGetHiddenState(bpy.context.scene)

        # Don't remove ignore_render, as we want to reuse this for collision
        self.sceneObj, allObjs = ootDuplicateHierarchy(self.originalSceneObj, None, True, OOTObjectCategorizer())

        if bpy.context.scene.exportHiddenGeometry:
            restoreHiddenState(hiddenState)

        try:
            altProp = self.sceneObj.ootAlternateSceneHeaders
            sceneData = OOTScene(self.sceneObj, self.transform, name=f"{toAlnum(self.sceneName)}_scene")
            sceneData.model = OOTModel(self.f3dType, self.isHWv1, f"{sceneData.name}_dl", self.dlFormat, False)
            altHeaderData = OOTSceneAlternateHeader(f"{sceneData.name}_alternateHeaders")
            sceneData.mainHeader = sceneData.getNewSceneHeader(self.sceneObj.ootSceneHeader)
            hasAltHeader = False

            for i, header in enumerate(altHeaderList, 1):
                altP: OOTSceneHeaderProperty = getattr(altProp, f"{header}Header")
                if not altP.usePreviousHeader:
                    setattr(altHeaderData, header, sceneData.getNewSceneHeader(altP, i))
                    hasAltHeader = True

            altHeaderData.cutscenes = [
                sceneData.getNewSceneHeader(csHeader, i) for i, csHeader in enumerate(altProp.cutsceneHeaders, 4)
            ]

            if len(altHeaderData.cutscenes) > 0:
                hasAltHeader = True

            sceneData.altHeader = altHeaderData if hasAltHeader else None
            sceneData.roomList = self.getNewRoomList(sceneData)
            sceneData.colHeader = sceneData.getNewCollisionHeader()
            sceneData.validateScene()

            if sceneData.mainHeader.cutscene is not None:
                self.hasCutscenes = sceneData.mainHeader.cutscene.writeCutscene

                if not self.hasCutscenes:
                    for cs in sceneData.altHeader.cutscenes:
                        if cs.cutscene.writeCutscene:
                            self.hasCutscenes = True
                            break

            ootCleanupScene(self.originalSceneObj, allObjs)
        except Exception as e:
            ootCleanupScene(self.originalSceneObj, allObjs)
            raise Exception(str(e))

        return sceneData

    def setRoomListData(self):
        """Gets and sets C data for every room elements"""

        for room in self.scene.roomList:
            roomMainData = room.getRoomMainC()
            roomModelData = room.getRoomShapeModelC(self.textureExportSettings)
            roomModelInfoData = room.roomShape.getRoomShapeC()

            self.header += roomMainData.header + roomModelData.header + roomModelInfoData.header
            self.roomList[room.roomIndex] = OOTRoomData(
                room.name, roomMainData.source, roomModelData.source, roomModelInfoData.source
            )

    def setSceneData(self):
        """Gets and sets C data for every scene elements"""

        sceneMainData = self.scene.getSceneMainC()
        sceneCollisionData = self.scene.colHeader.getSceneCollisionC()
        sceneCutsceneData = self.scene.getSceneCutscenesC()
        sceneTexturesData = self.scene.getSceneTexturesC(self.textureExportSettings)

        self.header += (
            sceneMainData.header
            + "".join(cs.header for cs in sceneCutsceneData)
            + sceneCollisionData.header
            + sceneTexturesData.header
        )

        self.sceneData = OOTSceneData(
            sceneMainData.source,
            sceneCollisionData.source,
            [cs.source for cs in sceneCutsceneData],
            sceneTexturesData.source,
        )

    def setIncludeData(self):
        """Adds includes at the beginning of each file to write"""

        suffix = "\n\n"
        sceneInclude = f'\n#include "{self.scene.name}.h"\n'
        common = includeData["common"]
        # room = includeData["roomMain"]
        # roomShapeInfo = includeData["roomShapeInfo"]
        # scene = includeData["sceneMain"]
        # collision = includeData["collision"]
        # cutscene = includeData["cutscene"]
        room = ""
        roomShapeInfo = ""
        scene = ""
        collision = ""
        cutscene = ""

        common = (
            '#include "ultra64.h"\n'
            + '#include "z64.h"\n'
            + '#include "macros.h"\n'
            + '#include "segment_symbols.h"\n'
            + '#include "command_macros_base.h"\n'
            + '#include "z64cutscene_commands.h"\n'
            + '#include "variables.h"\n'
        )

        for roomData in self.roomList.values():
            if self.singleFileExport:
                common += room + roomShapeInfo + sceneInclude
                roomData.roomMain = common + suffix + roomData.roomMain
            else:
                roomData.roomMain = common + room + sceneInclude + suffix + roomData.roomMain
                roomData.roomModelInfo = common + roomShapeInfo + sceneInclude + suffix + roomData.roomModelInfo
                roomData.roomModel = common + sceneInclude + suffix + roomData.roomModel

        if self.singleFileExport:
            common += scene + collision + cutscene + sceneInclude
            self.sceneData.sceneMain = common + suffix + self.sceneData.sceneMain
        else:
            self.sceneData.sceneMain = common + scene + sceneInclude + suffix + self.sceneData.sceneMain
            self.sceneData.sceneCollision = common + collision + sceneInclude + suffix + self.sceneData.sceneCollision

            if self.hasCutscenes:
                for cs in self.sceneData.sceneCutscenes:
                    cs = cutscene + sceneInclude + suffix + cs

    def writeScene(self):
        """Write the scene to the chosen location"""

        for room in self.roomList.values():
            if self.singleFileExport:
                roomMainPath = f"{room.name}.c"
                room.roomMain += room.roomModelInfo + room.roomModel
            else:
                roomMainPath = f"{room.name}_main.c"
                writeFile(os.path.join(self.path, f"{room.name}_model_info.c"), room.roomModelInfo)
                writeFile(os.path.join(self.path, f"{room.name}_model.c"), room.roomModel)

            writeFile(os.path.join(self.path, roomMainPath), room.roomMain)

        if self.singleFileExport:
            sceneMainPath = f"{self.sceneBasePath}.c"
            self.sceneData.sceneMain += self.sceneData.sceneCollision
            if self.hasCutscenes:
                for i, cs in enumerate(self.sceneData.sceneCutscenes):
                    self.sceneData.sceneMain += cs
        else:
            sceneMainPath = f"{self.sceneBasePath}_main.c"
            writeFile(f"{self.sceneBasePath}_col.c", self.sceneData.sceneCollision)
            if self.hasCutscenes:
                for i, cs in enumerate(self.sceneData.sceneCutscenes):
                    writeFile(f"{self.sceneBasePath}_cs_{i}.c", cs)

        if self.hasSceneTextures:
            writeFile(f"{self.sceneBasePath}_tex.c", self.sceneData.sceneTextures)

        self.header += "\n#endif\n"
        writeFile(sceneMainPath, self.sceneData.sceneMain)
        writeFile(self.sceneBasePath + ".h", self.header)

        for room in self.scene.roomList:
            room.mesh.copyBgImages(self.path)

    def export(self):
        """Main function"""

        checkObjectReference(self.originalSceneObj, "Scene object")
        isCustomExport = self.exportInfo.isCustomExportPath
        exportPath = self.exportInfo.exportPath

        exportSubdir = ""
        if self.exportInfo.customSubPath is not None:
            exportSubdir = self.exportInfo.customSubPath
        if not isCustomExport and self.exportInfo.customSubPath is None:
            exportSubdir = os.path.dirname(getSceneDirFromLevelName(self.sceneName))

        sceneInclude = exportSubdir + "/" + self.sceneName + "/"
        self.scene = self.getNewScene()
        self.path = ootGetPath(exportPath, isCustomExport, exportSubdir, self.sceneName, True, True)
        self.sceneBasePath = os.path.join(self.path, self.scene.name)
        self.textureExportSettings.includeDir = sceneInclude
        self.textureExportSettings.exportPath = self.path
        self.setSceneData()
        self.setRoomListData()
        self.hasSceneTextures = len(self.sceneData.sceneTextures) > 0

        if not isCustomExport:
            writeTextureArraysExistingScene(self.scene.model, exportPath, sceneInclude + self.sceneName + "_scene.h")
        else:
            textureArrayData = writeTextureArraysNew(self.scene.model, None)
            self.sceneData.sceneTextures += textureArrayData.source
            self.header += textureArrayData.header

        self.setIncludeData()
        self.writeScene()

        if not isCustomExport:
            Files(self).editFiles()

        if self.hackerootBootOption is not None and self.hackerootBootOption.bootToScene:
            setBootupScene(
                os.path.join(exportPath, "include/config/config_debug.h")
                if not isCustomExport
                else os.path.join(self.path, "config_bootup.h"),
                "ENTR_" + self.sceneName.upper() + "_" + str(self.hackerootBootOption.spawnIndex),
                self.hackerootBootOption,
            )
