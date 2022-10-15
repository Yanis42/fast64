from ....utility import PluginError
from ..utility import convertIntTo2sComplement
from ..classes.export import BoxEmpty


class OOTWaterBox(BoxEmpty):
    def __init__(self, roomIndex, lightingSetting, cameraSetting, position, scale, emptyScale):
        self.roomIndex = roomIndex
        self.lightingSetting = lightingSetting
        self.cameraSetting = cameraSetting
        BoxEmpty.__init__(self, position, scale, emptyScale)

    def propertyData(self):
        return f"(({self.roomIndex} << 13) | ({self.lightingSetting} << 8) | {self.cameraSetting})"


class OOTCameraPosData:
    def __init__(self, camSType, hasPositionData, position, rotation, fov, jfifID):
        self.camSType = camSType
        self.position = position
        self.rotation = rotation
        self.fov = fov
        self.jfifID = jfifID
        self.unknown = -1
        self.hasPositionData = hasPositionData


class OOTCameraData:
    def __init__(self, ownerName):
        self.ownerName = ownerName
        self.camPosDict: dict[int, OOTCameraPosData] = {}

    def camDataName(self):
        return self.ownerName + "_camData"

    def camPositionsName(self):
        return self.ownerName + "_camPosData"

    def validateCamPositions(self):
        count = 0
        while count < len(self.camPosDict):
            if count not in self.camPosDict:
                raise PluginError(
                    "Error: Camera positions do not have a consecutive list of indices.\n"
                    + "Missing index: "
                    + str(count)
                )
            count = count + 1


class OOTCollisionVertex:
    def __init__(self, position):
        self.position = position


class OOTCollisionPolygon:
    def __init__(self, indices, normal, distance):
        self.indices = indices
        self.normal = normal
        self.distance = distance

    def convertShort02(self, ignoreCamera, ignoreActor, ignoreProjectile):
        vertPart = self.indices[0] & 0x1FFF
        colPart = (1 if ignoreCamera else 0) + (2 if ignoreActor else 0) + (4 if ignoreProjectile else 0)

        return vertPart | (colPart << 13)

    def convertShort04(self, enableConveyor):
        vertPart = self.indices[1] & 0x1FFF
        conveyorPart = 1 if enableConveyor else 0

        return vertPart | (conveyorPart << 13)

    def convertShort06(self):
        return self.indices[2] & 0x1FFF


class OOTPolygonType:
    def __eq__(self, other):
        return (
            self.eponaBlock == other.eponaBlock
            and self.decreaseHeight == other.decreaseHeight
            and self.floorSetting == other.floorSetting
            and self.wallSetting == other.wallSetting
            and self.floorProperty == other.floorProperty
            and self.exitID == other.exitID
            and self.cameraID == other.cameraID
            and self.isWallDamage == other.isWallDamage
            and self.enableConveyor == other.enableConveyor
            and self.conveyorRotation == other.conveyorRotation
            and self.conveyorSpeed == other.conveyorSpeed
            and self.hookshotable == other.hookshotable
            and self.echo == other.echo
            and self.lightingSetting == other.lightingSetting
            and self.terrain == other.terrain
            and self.sound == other.sound
            and self.ignoreCameraCollision == other.ignoreCameraCollision
            and self.ignoreActorCollision == other.ignoreActorCollision
            and self.ignoreProjectileCollision == other.ignoreProjectileCollision
        )

    def __ne__(self, other):
        return (
            self.eponaBlock != other.eponaBlock
            or self.decreaseHeight != other.decreaseHeight
            or self.floorSetting != other.floorSetting
            or self.wallSetting != other.wallSetting
            or self.floorProperty != other.floorProperty
            or self.exitID != other.exitID
            or self.cameraID != other.cameraID
            or self.isWallDamage != other.isWallDamage
            or self.enableConveyor != other.enableConveyor
            or self.conveyorRotation != other.conveyorRotation
            or self.conveyorSpeed != other.conveyorSpeed
            or self.hookshotable != other.hookshotable
            or self.echo != other.echo
            or self.lightingSetting != other.lightingSetting
            or self.terrain != other.terrain
            or self.sound != other.sound
            or self.ignoreCameraCollision != other.ignoreCameraCollision
            or self.ignoreActorCollision != other.ignoreActorCollision
            or self.ignoreProjectileCollision != other.ignoreProjectileCollision
        )

    def __hash__(self):
        return hash(
            (
                self.eponaBlock,
                self.decreaseHeight,
                self.floorSetting,
                self.wallSetting,
                self.floorProperty,
                self.exitID,
                self.cameraID,
                self.isWallDamage,
                self.enableConveyor,
                self.conveyorRotation,
                self.conveyorSpeed,
                self.hookshotable,
                self.echo,
                self.lightingSetting,
                self.terrain,
                self.sound,
                self.ignoreCameraCollision,
                self.ignoreActorCollision,
                self.ignoreProjectileCollision,
            )
        )

    def __init__(self):
        self.eponaBlock = None  # eponaBlock
        self.decreaseHeight = None  # decreaseHeight
        self.floorSetting = None  # floorSetting
        self.wallSetting = None  # wallSetting
        self.floorProperty = None  # floorProperty
        self.exitID = None  # exitID
        self.cameraID = None  # cameraID
        self.isWallDamage = None  # isWallDamage
        self.enableConveyor = None
        self.conveyorRotation = None  # conveyorDirection
        self.conveyorSpeed = None  # conveyorSpeed
        self.hookshotable = None  # hookshotable
        self.echo = None  # echo
        self.lightingSetting = None  # lightingSetting
        self.terrain = None  # terrain
        self.sound = None  # sound
        self.ignoreCameraCollision = None
        self.ignoreActorCollision = None
        self.ignoreProjectileCollision = None

    def convertHigh(self):
        value = (
            ((1 if self.eponaBlock else 0) << 31)
            | ((1 if self.decreaseHeight else 0) << 30)
            | (int(self.floorSetting, 16) << 26)
            | (int(self.wallSetting, 16) << 21)
            | (int(self.floorProperty, 16) << 13)
            | (self.exitID << 8)
            | (self.cameraID << 0)
        )

        return convertIntTo2sComplement(value, 4, False)

    def convertLow(self):
        value = (
            ((1 if self.isWallDamage else 0) << 27)
            | (self.conveyorRotation << 21)
            | (self.conveyorSpeed << 18)
            | ((1 if self.hookshotable else 0) << 17)
            | (int(self.echo, 16) << 11)
            | (self.lightingSetting << 6)
            | (int(self.terrain, 16) << 4)
            | (int(self.sound, 16) << 0)
        )

        return convertIntTo2sComplement(value, 4, False)


class OOTCollision:
    def __init__(self, ownerName):
        self.ownerName = ownerName
        self.bounds: list[int] = []
        self.vertices: list[OOTCollisionVertex] = []
        # dict of polygon type : polygon list
        self.polygonGroups: dict[OOTPolygonType, list[OOTCollisionPolygon]] = {}
        self.cameraData = None
        self.waterBoxes = []

    def polygonCount(self):
        count = 0
        for polygonType, polygons in self.polygonGroups.items():
            count += len(polygons)
        return count

    def headerName(self):
        return self.ownerName + "_collisionHeader"

    def verticesName(self):
        return self.ownerName + "_vertices"

    def polygonsName(self):
        return self.ownerName + "_polygons"

    def polygonTypesName(self):
        return self.ownerName + "_polygonTypes"

    def camDataName(self):
        return self.ownerName + "_camData"

    def waterBoxesName(self):
        return self.ownerName + "_waterBoxes"
