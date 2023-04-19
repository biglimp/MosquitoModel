'''
This script is based on the geograpgy master thesis from Ville Stålnacke
at the Department of Earth Sciences, Univeristy of Gothenburg, 2021.
The model is designed to be executed with available Swedish geodata and
consist of four separate submodels plus an extract section defined by a
model domain. 

An additional script is availabe to create DSM, CDSM, LAI, land cover and DEM from 
NH Lidar data

Third party plugins required:
QuickOSM
Processing for UMEP
'''

from pathlib import Path
from osgeo import gdal
from qgis.core import QgsApplication, QgsProcessing, QgsCoordinateReferenceSystem
import numpy as np
from osgeo.gdalconst import GA_ReadOnly
import sys, os
import shutil
from misc import saveraster
import time
# import matplotlib.pylab as plt

# Initiating a QGIS application and connect to processing
qgishome = 'C:/OSGeo4W/apps/qgis/' # Path to osgeo installation
QgsApplication.setPrefixPath(qgishome, True)
app = QgsApplication([], False)
app.initQgis()

sys.path.append(r'C:\OSGeo4W\apps\qgis\python\plugins') # Path to qgis core plugins
sys.path.append(r'C:\Users\xlinfr\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins') # Path to third party plugins

import processing
from processing_umep.processing_umep_provider import ProcessingUMEPProvider
umep_provider = ProcessingUMEPProvider()
QgsApplication.processingRegistry().addProvider(umep_provider)

from processing.core.Processing import Processing
Processing.initialize()

import heatmappart

import warnings
warnings.filterwarnings("ignore")

#internal functions
# mosaic funktion. Requires same size rasters
def mosaicrasters(textfile, outfile):
    i = 0
    with open(textfile) as file:
        for line in file:
            baseraster = gdal.Open(line[:-1]) #-1 to remove \n
            nd = baseraster.GetRasterBand(1).GetNoDataValue()
            if i == 0:
                raster = baseraster.ReadAsArray().astype(np.float)
                raster[raster == nd] = 0
            else:
                raster1 = baseraster.ReadAsArray().astype(np.float)
                raster1[raster1 == nd] = 0
                raster = np.maximum(raster, raster1)
            i = i + 1
    saveraster(baseraster, outfile, raster)

start = time.time()

#INPUTDATA AND SETTINGS (Geodata should be in same CRS (ESPG:3006))
datafolder = 'D:/TRANSAFE/Uppsala/' 
NMDdata = 'D:/TRANSAFE/Data/Data/NMD-data/'
tempfolder = 'D:/TRANSAFE/Uppsala/tempdata/' # data where temporary data is saved. Is deleted at each run
mergedfolder = 'mergeoutput/' # intermediate folder
outputfolder = datafolder + 'OutSkog_changedHeatmap/'
baseDSM = datafolder + mergedfolder + 'dsm.tif' #Ground and building DSM from NH lidar
baseDEM = datafolder + mergedfolder + 'dem.tif' #Ground elevation model from NH lidar
baseCDSM = datafolder + mergedfolder + 'cdsm.tif' #Vegetation canopy model from NH lidar
baselai = datafolder + mergedfolder + 'lai.tif' #Leaf area index from NH lidar
studyarea = datafolder +  'domain.shp' # model domain. Final clip to remove edge areas.
landuse =  datafolder + 'InData/Fastighetskartan_Markdata/my_middle.shp' #LM Fastighetskaratan (my)
buildings = datafolder + 'InData/Fastighetskartan_Bebyggelse/by_03.shp' #LM Fastighetskartan (by)
manmade_areas = NMDdata + 'NMD-Markanvandning/NMD_markanv_anlagda_omr_v1.tif' # NMD markanvändning
gracing = NMDdata + 'NMD-Markanvandning/NMD_markanv_bete_v1.tif' # NMD markanvändning
powerlines = NMDdata + 'NMD-Markanvandning/NMD_markanv_kraftledning_v1.tif' # NMD markanvändning
landcover = NMDdata + 'NMD/nmd2018bas_ogeneraliserad_v1_1.tif' # NMD marktäckedata
objectheight0to5 =  NMDdata  + 'NMDObjektHojd/0_5t5/objekt_hojd_intervall_0_5_till_5_v1_3.img' # NMD objekthöjdsdata 5
objectheight5to45 = NMDdata + 'NMDObjektHojd/5t45/objekt_hojd_intervall_5_till_45_v1_3.img' # NMD objekthöjdsdata 45
oceanDist = 'G:/TRANSAFEDATA/distanceToOcean_v2.tif' #Calcuatated distance from sea in landcover = 62. Set to '' if not exist. Take a long time to calculate.
useoldheatmaps = 0  # Change this to zero if any changes are made in input data from previous run. Takes a long time to calcualte.
demOffset = 0.0  #10.07 (GBG nätet). Special case
manmadeAdditions = datafolder + 'InData/TillaggUppsala.shp' # adding missing areas in Manmade in attribute "typ". Set to None if no changes are neccecary.

#Do not change anything below here
print('### MODEL START ###')
results = {}
outputs = {}

if os.path.exists(tempfolder):
    shutil.rmtree(tempfolder)
os.mkdir(tempfolder)

inDSM = tempfolder + 'clipdsm.tif'
inDEM = tempfolder + 'clipdem.tif'
inCDSM = tempfolder + 'clipcdsm.tif'
inBuild = tempfolder + 'buildraster.tif'
inBuildbool = tempfolder + 'buildbool.tif'
inVegbool = tempfolder + 'vegbool.tif'
inLAI = tempfolder + 'lai.tif'

print('clipping data to model extent') 
alg_params = {'INPUT':landcover,
    'MASK':studyarea,
    'SOURCE_CRS':None,'TARGET_CRS':None,'TARGET_EXTENT':None,'NODATA':None,'ALPHA_BAND':False,'CROP_TO_CUTLINE':True,'KEEP_RESOLUTION':False,'SET_RESOLUTION':False,'X_RESOLUTION':None,'Y_RESOLUTION':None,'MULTITHREADING':False,'OPTIONS':'','DATA_TYPE':0,'EXTRA':'','OUTPUT':'TEMPORARY_OUTPUT'}
outputs['ClipLandcover'] = processing.run("gdal:cliprasterbymasklayer", alg_params) # this is used to clip other data from here on

data = gdal.Open(outputs['ClipLandcover']['OUTPUT'], GA_ReadOnly)
geoTransform = data.GetGeoTransform()
minx = geoTransform[0]
maxy = geoTransform[3]
maxx = minx + geoTransform[1] * data.RasterXSize
miny = maxy + geoTransform[5] * data.RasterYSize
data = None
projwin = str(minx) + ',' + str(maxx) + ',' + str(miny) +',' + str(maxy) + ' [EPSG:3006]'

alg_params = {'INPUT':manmade_areas,
    'PROJWIN':projwin,'OVERCRS':False,'NODATA':None,'OPTIONS':'','DATA_TYPE':0,'EXTRA':'',
    'OUTPUT':tempfolder + 'manmade.tif'}
outputs['ClipManmade']  = processing.run("gdal:cliprasterbyextent", alg_params)
alg_params = {'INPUT':powerlines,
    'PROJWIN':projwin,'OVERCRS':False,'NODATA':None,'OPTIONS':'','DATA_TYPE':0,'EXTRA':'',
    'OUTPUT':tempfolder + 'powerlines.tif'}
outputs['ClipPowerlines']  = processing.run("gdal:cliprasterbyextent", alg_params)
alg_params = {'INPUT':gracing,
    'PROJWIN':projwin,'OVERCRS':False,'NODATA':None,'OPTIONS':'','DATA_TYPE':0,'EXTRA':'',
    'OUTPUT':tempfolder + 'gracing.tif'}
outputs['ClipGracing']  = processing.run("gdal:cliprasterbyextent", alg_params)
alg_params = {'INPUT':baseDSM,
    'PROJWIN':projwin,'OVERCRS':False,'NODATA':None,'OPTIONS':'','DATA_TYPE':0,'EXTRA':'',
    'OUTPUT':inDSM}
outputs['ClipDSM']  = processing.run("gdal:cliprasterbyextent", alg_params)
alg_params = {'INPUT':baseDEM,
    'PROJWIN':projwin,'OVERCRS':False,'NODATA':None,'OPTIONS':'','DATA_TYPE':0,'EXTRA':'',
    'OUTPUT':inDEM}
outputs['ClipDEM']  = processing.run("gdal:cliprasterbyextent", alg_params)
alg_params = {'INPUT':baseCDSM,
    'PROJWIN':projwin,'OVERCRS':False,'NODATA':None,'OPTIONS':'','DATA_TYPE':0,'EXTRA':'',
    'OUTPUT':inCDSM}
outputs['ClipCDSM']  = processing.run("gdal:cliprasterbyextent", alg_params)
alg_params = {'INPUT':baselai,
    'PROJWIN':projwin,'OVERCRS':False,'NODATA':None,'OPTIONS':'','DATA_TYPE':0,'EXTRA':'',
    'OUTPUT':inLAI}
outputs['ClipLAI']  = processing.run("gdal:cliprasterbyextent", alg_params)
alg_params = {'INPUT':objectheight0to5,
    'PROJWIN':projwin,'OVERCRS':False,'NODATA':None,'OPTIONS':'','DATA_TYPE':0,'EXTRA':'',
    'OUTPUT':'TEMPORARY_OUTPUT'}
outputs['ClipHeight0to5'] = processing.run("gdal:cliprasterbyextent", alg_params)
alg_params = {'INPUT':objectheight5to45,
    'PROJWIN':projwin,'OVERCRS':False,'NODATA':None,'OPTIONS':'','DATA_TYPE':0,'EXTRA':'',
    'OUTPUT':'TEMPORARY_OUTPUT'}
outputs['ClipHeight5to45'] = processing.run("gdal:cliprasterbyextent", alg_params)

if not manmadeAdditions == None:
    alg_params = {
        'INPUT':'D:/TRANSAFE/Uppsala/InData/TillaggUppsala.shp',
        'INPUT_RASTER':'D:/TRANSAFE/Uppsala/tempdata/manmade.tif',
        'FIELD':'typ',
        'ADD':True,
        'EXTRA':''
        }
    processing.run("gdal:rasterize_over", alg_params)

if oceanDist == '':
    print('Proximity (raster distance) - Distance from ocean. Takes a long time')
    alg_params = {
        'BAND': 1,
        'DATA_TYPE': 5,
        'EXTRA': '',
        'INPUT': landcover,
        'MAX_DISTANCE': 30000,
        'NODATA': 0,
        'OPTIONS': '',
        'REPLACE': 0,
        'UNITS': 0,
        'VALUES': '62',
        'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
    }
    outputs['ProximityRasterDistanceDistanceFromOceantemp'] = processing.run('gdal:proximity', alg_params)

    alg_params = {'INPUT':outputs['ProximityRasterDistanceDistanceFromOcean']['OUTPUT'],
        'PROJWIN':projwin,'OVERCRS':False,'NODATA':None,'OPTIONS':'','DATA_TYPE':0,'EXTRA':'',
        'OUTPUT':tempfolder + 'distocean.tif'}
    outputs['ProximityRasterDistanceDistanceFromOcean'] = processing.run("gdal:cliprasterbyextent", alg_params)
else:
    alg_params = {'INPUT':oceanDist,
        'PROJWIN':projwin,'OVERCRS':False,'NODATA':None,'OPTIONS':'','DATA_TYPE':0,'EXTRA':'',
        'OUTPUT':tempfolder + 'distocean.tif'}
    outputs['ProximityRasterDistanceDistanceFromOcean'] = processing.run("gdal:cliprasterbyextent", alg_params)


# Create building and veg bool grid
baseraster = gdal.Open(inDEM)
demraster = baseraster.ReadAsArray().astype(np.float)
baseraster = gdal.Open(inDSM)
geotransform = baseraster.GetGeoTransform()
cellsize = geotransform[1]
dsmraster = baseraster.ReadAsArray().astype(np.float)
buildraster = dsmraster - (demraster - demOffset)
buildraster[buildraster < 0.5] = 0
saveraster(baseraster, inBuild, buildraster)
saveraster(baseraster, inBuildbool, buildraster > 0)
baseraster = gdal.Open(inCDSM)
cdsmraster = baseraster.ReadAsArray().astype(np.float)
saveraster(baseraster, inVegbool, cdsmraster > 0)
baseraster = None

print('### THE IUHD MODEL ###')
print('Calculates wall heights. Disregard the wall aspect output.') 
if not os.path.exists(datafolder + 'wallheight.tif'):
    alg_params = {
        'INPUT': inDSM,
        'INPUT_LIMIT': 2.0,
        'OUTPUT_HEIGHT': datafolder + 'wallheight.tif'
    }
    outputs['UrbanGeometryWallHeightAndAspect'] = processing.run('umep:Urban Geometry: Wall Height and Aspect', alg_params)
else:
    outputs['UrbanGeometryWallHeightAndAspect'] = {'OUTPUT_HEIGHT':datafolder + 'wallheight.tif'}

print('Create grid')
alg_params = {
    'CRS': 'ProjectCrs',
    'EXTENT': projwin,
    'HOVERLAY': 0,
    'HSPACING': 100,
    'TYPE': 2,  # Rectangle (Polygon)
    'VOVERLAY': 0,
    'VSPACING': 100, 
    'OUTPUT': tempfolder + 'grid.shp' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['CreateGrid'] = processing.run('native:creategrid', alg_params)


print('Add geometry attributes')
# Adds geometric attributes to the grid, of which "area" will be used further in the model. 
alg_params = {
    'CALC_METHOD': 0,  # Layer CRS
    'INPUT': tempfolder + 'grid.shp', #outputs['CreateGrid']['OUTPUT'],
    'OUTPUT': tempfolder + 'gridstat1.shp' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['AddGeometryAttributes'] = processing.run('qgis:exportaddgeometrycolumns', alg_params)


print('Zonal statistics Wall area')
alg_params = {
    'COLUMN_PREFIX': '_wa',
    'INPUT_RASTER': outputs['UrbanGeometryWallHeightAndAspect']['OUTPUT_HEIGHT'],
    'INPUT_VECTOR': outputs['AddGeometryAttributes']['OUTPUT'],
    'RASTER_BAND': 1,
    'STATISTICS': [1],  # Sum
}
outputs['ZonalStatistics'] = processing.run('native:zonalstatistics', alg_params)


print('Field calculator WallAreaFraction, Calculates wall area fraction.')
alg_params = {
    'FIELD_LENGTH': 10,
    'FIELD_NAME': 'wai', #'WallAreaFraction',
    'FIELD_PRECISION': 3,
    'FIELD_TYPE': 0,  # Decimal (double)
    'FORMULA': '("_wasum" * ' + str(cellsize) + ') / "area"',
    'INPUT': outputs['ZonalStatistics']['INPUT_VECTOR'],
    'OUTPUT': tempfolder + 'gridstat2.shp' #QgsProcessing.TEMPORARY_OUTPUT #
}
print('("_wasum" * ' + str(cellsize) + ') / "area"')
outputs['FieldCalculatorWallareafraction'] = processing.run('native:fieldcalculator', alg_params)


print('Zonal statistics building plan area')
alg_params = {
    'COLUMN_PREFIX': '_pai',
    'INPUT_RASTER': inBuildbool,
    'INPUT_VECTOR': outputs['FieldCalculatorWallareafraction']['OUTPUT'], #tempfolder + 'gridstat2.shp', # 
    'RASTER_BAND': 1,
    'STATISTICS': [0, 1],  # Sum and Count
}
outputs['ZonalStatistics'] = processing.run('native:zonalstatistics', alg_params)


print('Field calculator PlanAreaFraction, Calculates building footprint fraction.')
alg_params = {
    'FIELD_LENGTH': 10,
    'FIELD_NAME': 'pai', 
    'FIELD_PRECISION': 3,
    'FIELD_TYPE': 0,  # Decimal (double)
    'FORMULA': '"_paisum" / "_paicount"',
    'INPUT': tempfolder + 'gridstat2.shp', #outputs['FieldCalculatorWallareafraction']['OUTPUT'], #
    'OUTPUT': tempfolder + 'gridstat3.shp', #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['FieldCalculatorPlanareafraction'] = processing.run('native:fieldcalculator', alg_params)

print('Field calculator HW, Calculates HW-ratio')
alg_params = {
    'FIELD_LENGTH': 10,
    'FIELD_NAME': 'HW',
    'FIELD_PRECISION': 3,
    'FIELD_TYPE': 0,  # Decimal (double)
    'FORMULA': '( "wai" * "pai") / ((2 * "pai") * (1 - "pai"))',
    'INPUT': outputs['FieldCalculatorPlanareafraction']['OUTPUT'],
    'OUTPUT': tempfolder + 'gridstat4.shp', #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['FieldCalculatorHw'] = processing.run('native:fieldcalculator', alg_params)

# Field calculator HW Decreased. Remove extreme HW-values (>3)
alg_params = {
    'FIELD_LENGTH': 10,
    'FIELD_NAME': 'HWDecr',
    'FIELD_PRECISION': 3,
    'FIELD_TYPE': 0,  # Decimal (double)
    'FORMULA': 'CASE WHEN ("HW" > 3) THEN 3 ELSE "HW" END ',
    'INPUT': outputs['FieldCalculatorHw']['OUTPUT'],
    'OUTPUT': tempfolder + 'gridstat5.shp' # 'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
}
outputs['FieldCalculatorHwDecreased'] = processing.run('native:fieldcalculator', alg_params)


print('Zonal grid statistics vegetation plan area')
alg_params = {
    'COLUMN_PREFIX': '_paiv',
    'INPUT_RASTER': inVegbool,
    'INPUT_VECTOR': outputs['FieldCalculatorHwDecreased']['OUTPUT'], #tempfolder + 'gridstat.shp', # outputs['AddGeometryAttributes']['OUTPUT'],
    'RASTER_BAND': 1,
    'STATISTICS': [0, 1],  # Sum and Count
}
outputs['ZonalStatistics'] = processing.run('native:zonalstatistics', alg_params)


print('Field calculator Veg PlanAreaFraction, Calculates Tree footprint fraction.')
alg_params = {
    'FIELD_LENGTH': 10,
    'FIELD_NAME': 'paiveg', 
    'FIELD_PRECISION': 3,
    'FIELD_TYPE': 0,  # Decimal (double)
    'FORMULA': '"_paivsum" / "_paivcount"',
    'INPUT': tempfolder + 'gridstat5.shp',
    'OUTPUT': tempfolder + 'gridstat6.shp', #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['FieldCalculatorVegplanareafraction'] = processing.run('native:fieldcalculator', alg_params)


print('Field calculator VegCooling. Calculates the cooling effect of the vegetation') 
alg_params = {
    'FIELD_LENGTH': 10,
    'FIELD_NAME': 'VegCooling',
    'FIELD_PRECISION': 3,
    'FIELD_TYPE': 0,  # Decimal (double)
    'FORMULA': '(("paiveg" / 0.1) * 0.3)',
    'INPUT': outputs['FieldCalculatorVegplanareafraction']['OUTPUT'],
    'OUTPUT': tempfolder + 'gridstat7.shp'
}
outputs['FieldCalculatorVegcooling'] = processing.run('native:fieldcalculator', alg_params)


print('Field calculator HW-warming. Calculates the warming effect of HW-ratio')
alg_params = {
    'FIELD_LENGTH': 10,
    'FIELD_NAME': 'UHIMaxHW',
    'FIELD_PRECISION': 3,
    'FIELD_TYPE': 0,  # Decimal (double)
    'FORMULA': '7.54 + 3.97 * (ln( "HWDecr" ))',
    'INPUT': outputs['FieldCalculatorVegcooling']['OUTPUT'],
    'OUTPUT': tempfolder + 'gridstat8.shp' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['FieldCalculatorHwwarming'] = processing.run('native:fieldcalculator', alg_params)


print('Field calculator Remove Null')
alg_params = {
    'FIELD_LENGTH': 10,
    'FIELD_NAME': 'UHIMaxHWNN',
    'FIELD_PRECISION': 3,
    'FIELD_TYPE': 0,  # Decimal (double)
    'FORMULA': 'CASE WHEN "UHIMaxHW" IS null THEN 0 ELSE "UHIMaxHW" END ',
    'INPUT': outputs['FieldCalculatorHwwarming']['OUTPUT'],
    'OUTPUT': tempfolder + 'gridstat9.shp' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['FieldCalculatorRemoveNull'] = processing.run('native:fieldcalculator', alg_params)


print('Field calculator Remove Negative HW-warm')
alg_params = {
    'FIELD_LENGTH': 10,
    'FIELD_NAME': 'UHIMaxNoNe',
    'FIELD_PRECISION': 3,
    'FIELD_TYPE': 0,  # Decimal (double)
    'FORMULA': 'CASE WHEN "UHIMaxHWNN" < 0 THEN 0 ELSE  "UHIMaxHWNN" END ',
    'INPUT': outputs['FieldCalculatorRemoveNull']['OUTPUT'],
    'OUTPUT': tempfolder + 'gridstat10.shp' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['FieldCalculatorRemoveNegativeHwwarm'] = processing.run('native:fieldcalculator', alg_params)


# Field calculator IUHD
alg_params = {
    'FIELD_LENGTH': 10,
    'FIELD_NAME': 'IUHD',
    'FIELD_PRECISION': 3,
    'FIELD_TYPE': 0,  # Decimal (double)
    'FORMULA': '"UHIMaxNoNe" - "VegCooling"',
    'INPUT': outputs['FieldCalculatorRemoveNegativeHwwarm']['OUTPUT'],
    'OUTPUT': tempfolder + 'grid_iuhd.shp' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['FieldCalculatorIuhd'] = processing.run('native:fieldcalculator', alg_params)


print('Rasterize (vector to raster) - IUHD')
alg_params = {
    'BURN': 0,
    'DATA_TYPE': 5,
    'EXTENT': projwin,
    'EXTRA': '',
    'FIELD': 'IUHD',
    'HEIGHT': 10,
    'INIT': None,
    'INPUT': outputs['FieldCalculatorIuhd']['OUTPUT'],
    'INVERT': False,
    'NODATA': None,
    'OPTIONS': '',
    'UNITS': 1,
    'WIDTH': 10,
    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
}
outputs['RasterizeVectorToRasterUUHD'] = processing.run('gdal:rasterize', alg_params)


print('Reclassify UHID')
iuhdtable = [
    -3.0,-2.33,1,
    -2.33,-1.66,2,
    -1.66,-0.99,3,
    -0.99,-0.33,4,
    -0.33,0.33,5,
    0.33,1.0,6,
    1.0,1.66,7,
    1.66,2.33,8,
    2.33,3.0,9,
    3.0,100.0,10,
]
alg_params = {
    'INPUT_RASTER':outputs['RasterizeVectorToRasterUUHD']['OUTPUT'],
    'RASTER_BAND':1,
    'TABLE':iuhdtable,
    'NO_DATA':-9999,
    'RANGE_BOUNDARIES':0,
    'NODATA_FOR_MISSING':False,
    'DATA_TYPE':3,
    'OUTPUT': tempfolder + 'IUHD_final.tif' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['ReclassifyValuesSimpleIUHD'] = processing.run("native:reclassifybytable", alg_params)



print('### THE OVIPOSITION MODEL ###')

print('Clip land use data for OVI model')
alg_params = { 
    'INPUT' : landuse, 
    'OUTPUT' : tempfolder + 'clipLU.shp', #QgsProcessing.TEMPORARY_OUTPUT, 
    'OVERLAY' : studyarea 
}
outputs['ClipLandUse'] = processing.run("native:clip", alg_params)


print('Extract by expression - industries. # Extract industrial areas from land use vector')
alg_params = {
    'EXPRESSION': ' \"DETALJTYP\" LIKE \'BEBIND\' ',
    'INPUT': outputs['ClipLandUse']['OUTPUT'],
    'OUTPUT': tempfolder + 'ExtractByExpressionIndustries.shp' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['ExtractByExpressionIndustries'] = processing.run('native:extractbyexpression', alg_params)

print('Clip building data for OVI model')
alg_params = { 
    'INPUT' : buildings, 
    'OUTPUT' : tempfolder + 'ClipBuildings.shp', 
    'OVERLAY' : studyarea 
}
outputs['ClipBuildings'] = processing.run("native:clip", alg_params)

print('Extract by expression - buildings, Extracts "Småhus" from the building layer.') 
alg_params = {
    'EXPRESSION': ' "ANDAMAL_1T" LIKE \'Bostad; Småhus%\' ', # ' \"ANDAMAL_1T\"  LIKE \'%Bostad; Sm?hus%\' ',
    'INPUT': outputs['ClipBuildings']['OUTPUT'],
    'OUTPUT': tempfolder + 'ExtractByExpressionBuildings.shp' # QgsProcessing.TEMPORARY_OUTPUT
}
outputs['ExtractByExpressionBuildings'] = processing.run('native:extractbyexpression', alg_params)


print('Buffer. Creates a buffer of 10 meters around all "sm�hus", which will represent residential gardens.')
alg_params = {
    'DISSOLVE': False,
    'DISTANCE': 10,
    'END_CAP_STYLE': 0,
    'INPUT': outputs['ExtractByExpressionBuildings']['OUTPUT'],
    'JOIN_STYLE': 0,
    'MITER_LIMIT': 2,
    'SEGMENTS': 5,
    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
}
outputs['Buffer'] = processing.run('native:buffer', alg_params)


print('Rasterize (vector to raster) - industries')
alg_params = {
    'BURN': 16,
    'DATA_TYPE': 5,
    'EXTENT': projwin,
    'EXTRA': '',
    'FIELD': '',
    'HEIGHT': 10,
    'INIT': None,
    'INPUT': outputs['ExtractByExpressionIndustries']['OUTPUT'],
    'INVERT': False,
    'NODATA': 0,
    'OPTIONS': '',
    'UNITS': 1,
    'WIDTH': 10,
    'OUTPUT': tempfolder + 'indu.tif' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['RasterizeVectorToRasterIndustries'] = processing.run('gdal:rasterize', alg_params)


print('Slope of rooftops')
alg_params = {
    'AS_PERCENT': False,
    'BAND': 1,
    'COMPUTE_EDGES': False,
    'EXTRA': '',
    'INPUT': inDSM,
    'OPTIONS': '',
    'SCALE': 1,
    'ZEVENBERGEN': False,
    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
}
outputs['SlopeOfRooftopstemp'] = processing.run('gdal:slope', alg_params)


print('Mask out roofs only from slope')
# hereafter replaced qgis:rastercalculator to gdal:rastercalculator
alg_params = { 
    'BAND_A' : 1, 
    'BAND_B' : None, 
    'BAND_C' : None, 
    'BAND_D' : None, 
    'BAND_E' : None, 
    'BAND_F' : None, 
    'EXTRA' : '', 
    'FORMULA' : '(A == 0) * 100 + + (A == 1) * B', 
    'INPUT_A' : inBuildbool, 
    'INPUT_B' : outputs['SlopeOfRooftopstemp']['OUTPUT'], 
    'INPUT_C' : None, 
    'INPUT_D' : None, 
    'INPUT_E' : None, 
    'INPUT_F' : None, 
    'NO_DATA' : 130, 
    'OPTIONS' : '', 
    'OUTPUT' : tempfolder + 'testslope.tif', # QgsProcessing.TEMPORARY_OUTPUT, 
    'PROJWIN' : None, 
    'RTYPE' : 5 
}
outputs['SlopeOfRooftops'] = processing.run("gdal:rastercalculator", alg_params)


print('Warp (reproject) Testing All slopes to 10m res')
alg_params = {
    'DATA_TYPE': 0,
    'EXTRA': '',
    'INPUT': outputs['SlopeOfRooftops']['OUTPUT'],
    'MULTITHREADING': False,
    'NODATA': None,
    'OPTIONS': '',
    'RESAMPLING': 0,
    'SOURCE_CRS': 'ProjectCrs',
    'TARGET_CRS': 'ProjectCrs',
    'TARGET_EXTENT': projwin,
    'TARGET_EXTENT_CRS': None,
    'TARGET_RESOLUTION': 10,
    'OUTPUT': tempfolder + 'warp.tif' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['WarpReprojectTestingAllSlopesTo10mRes'] = processing.run('gdal:warpreproject', alg_params)

print('Raster calculator - Sets slopes > 8 to nodata. Turns all rooftops with sloper > 8� to nodata, '
      'as they are to steep to be oviposition sites.')
# hereafter replaced qgis:rastercalculator to gdal:rastercalculator
alg_params = { 
    'BAND_A' : 1, 
    'BAND_B' : None, 
    'BAND_C' : None, 
    'BAND_D' : None, 
    'BAND_E' : None, 
    'BAND_F' : None, 
    'EXTRA' : '', 
    'FORMULA' : '(A < 8) * A + (A >= 8) * 130', 
    'INPUT_A' : outputs['WarpReprojectTestingAllSlopesTo10mRes']['OUTPUT'], 
    'INPUT_B' : None, 
    'INPUT_C' : None, 
    'INPUT_D' : None, 
    'INPUT_E' : None, 
    'INPUT_F' : None, 
    'NO_DATA' : 130, 
    'OPTIONS' : '', 
    'OUTPUT' : tempfolder + 'test.tif', # QgsProcessing.TEMPORARY_OUTPUT, 
    'PROJWIN' : None, 
    'RTYPE' : 5 
}
outputs['RasterCalculatorSetsSlopes8ToNodata'] = processing.run("gdal:rastercalculator", alg_params)


print('Rasterize (vector to raster) - Gardens, Rasterizes the buffer of residential gardens.') 
alg_params = {
    'BURN': 15,
    'DATA_TYPE': 5,
    'EXTENT': projwin,
    'EXTRA': '',
    'FIELD': '',
    'HEIGHT': 10,
    'INIT': None,
    'INPUT': outputs['Buffer']['OUTPUT'],
    'INVERT': False,
    'NODATA': 0,
    'OPTIONS': '',
    'UNITS': 1,
    'WIDTH': 10,
    'OUTPUT': tempfolder + 'garden.tif' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['RasterizeVectorToRasterGardens'] = processing.run('gdal:rasterize', alg_params)


print('Reclassify values (range) - reclassifies slopes =< 8. Reclassifies rooftops to value 129. The value is chosen to make sure that rooftops are joined correctly with the land cover layer. NMD land cover has maximum value of 128, and by using the setting "maximum" for overlapping pixels (in the next step), rooftops will be prioritized.')
# replaced saga with grass reclassifier
alg_params = {
    'input' : outputs['RasterCalculatorSetsSlopes8ToNodata']['OUTPUT'],
    'rules' : '',
    'txtrules':'0 thru 90 = 129',
    'output' : QgsProcessing.TEMPORARY_OUTPUT,
    'GRASS_REGION_PARAMETER' : None,
    'GRASS_REGION_CELLSIZE_PARAMETER' : 0,
    'GRASS_RASTER_FORMAT_OPT' : '',
    'GRASS_RASTER_FORMAT_META' : ''
}
outputs['ReclassifyValuesRangeReclassifiesSlopes8'] = processing.run("grass7:r.reclass",alg_params)

print('Mosaic raster layers - Land uses')
#creating file list text file 
with open(tempfolder + 'mosaicLU.txt', 'w') as file:
    file.write(str(Path(outputs['ClipGracing']['OUTPUT'])))
    file.write('\n')
    file.write(str(Path(outputs['ClipManmade']['OUTPUT'])))
    file.write('\n')
    file.write(str(Path(outputs['ClipPowerlines']['OUTPUT'])))
    file.write('\n')
    file.write(str(Path(outputs['RasterizeVectorToRasterGardens']['OUTPUT'])))
    file.write('\n')
    file.write(str(Path(outputs['RasterizeVectorToRasterIndustries']['OUTPUT'])))
    file.write('\n')
    file.close()

mosaicrasters(tempfolder + 'mosaicLU.txt', tempfolder + 'mosaicLU.tif')
outputs['MosaicRasterLayersLandUses'] = {'TARGET_OUT_GRID': tempfolder + 'mosaicLU.tif'}


print('Mosaic raster layers - Land cover')
#creating file list text file 
with open(tempfolder + 'mosaicLC.txt', 'w') as file:
    file.write(str(Path(outputs['ClipLandcover']['OUTPUT'])))
    file.write('\n')
    file.write(str(Path(outputs['ReclassifyValuesRangeReclassifiesSlopes8']['output'])))
    file.write('\n')
    file.close()

mosaicrasters(tempfolder + 'mosaicLC.txt', tempfolder + 'mosaicLC.tif')
outputs['MosaicRasterLayersLandCover']  = {'TARGET_OUT_GRID': tempfolder + 'mosaicLC.tif'}


print('remove nodata from land use')
alg_params = { 
    'BAND' : 1, 
    'FILL_VALUE' : 0, 
    'INPUT' : outputs['MosaicRasterLayersLandUses']['TARGET_OUT_GRID'], 
    'OUTPUT' : tempfolder + 'mosaicLUND.tif' #QgsProcessing.TEMPORARY_OUTPUT  
}
outputs['MosaicRasterLayersLandCoverND'] = processing.run("native:fillnodata", alg_params)

alg_params = { 
    'INPUT': outputs['MosaicRasterLayersLandUses']['TARGET_OUT_GRID'],
    'CRS':QgsCoordinateReferenceSystem('EPSG:3006')
}
processing.run("gdal:assignprojection", alg_params)


print('Reclassify values (simple) - LAND COVER') #Moved to native:reclassifybytable
#Landcover reclassifying table
lctable = [
    1,2,7,          # Open wetland
    2,3,4,          # Arable land
    40,41,2,        # Non-vegetated other open land
    41,42,4,        # Vegetated other open land
    50,51,1,        # Artificial surfaces, building
    51,52,3,        # Artificial surfaces, not building or road/railway 
    52,53,0,        # Road or railway. 
    60,61,0,        # Lakes or water-courses
    61,62,0,        # Sea, ocean, estuaries or coastal lagoons.
    110,111,4,      # Pine forest not on wetland
    111,112,4,      # Spruce forest not on wetland
    112,113,4,      # Mixed coniferous not on wetland
    113,114,5,      # Mixed forest not on wetland CHANGE?
    114,115,5,      # 115 Deciduous forest not on wetland CHANGE?
    115,116,6,      # Deciduous hardwood forest not on wetland CHANGE?
    116,117,6,      # Deciduous forest with deciduous hardwood forest not on wetland CHANGE?
    117,118,4,      # Temporarily non-forest not on wetland
    120,121,6,      # Pine forest on wetland
    121,122,6,      # Spruce forest on wetland
    122,123,6,      # Mixed coniferous on wetland
    123,124,7,      # Mixed forest on wetland
    124,125,7,      # Deciduous forest on wetland
    125,126,9,      # Deciduous hardwood forest on wetland
    126,127,8,      # Deciduous forest with deciduous hardwood forest on wetland
    127,128,6,      # Temporarily non-forest on wetland
    128,129,4       # Slopes on roofs less than 8 degrees (see above) ???
]
alg_params = {
    'INPUT_RASTER':outputs['MosaicRasterLayersLandCover']['TARGET_OUT_GRID'],
    'RASTER_BAND':1,
    'TABLE':lctable,
    'NO_DATA':-9999,
    'RANGE_BOUNDARIES':0, #min < value =< max
    'NODATA_FOR_MISSING':False,
    'DATA_TYPE':3,
    'OUTPUT': tempfolder + 'reclassLC.tif' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['ReclassifyValuesSimpleLandCover'] = processing.run("native:reclassifybytable", alg_params)

print('Reclassify values (simple) - LAND USE')
lutable = [
    -1,0,5,     # No specific land use. Changed to 5(or 6) (from 3) to be equal in weighting with land cover
    0,1,2,      # Airport
    1,2,5,      # Cemeneries  # change from 9 (Villes thesis)
    2,3,6,      # Quarries
    3,4,4,      # Peat extraction site
    4,5,5,      # Mining area
    5,6,5,      # Gracing area
    6,7,5,      # Power lines
    7,8,9,      # Alltment gardens
    8,9,7,      # Camping site
    9,10,6,     # Golf course
    10,11,5,    # Ski slope
    11,12,2,    # Motor racing track
    12,13,3,    # Sports facitily
    13,14,6,    # Waste and recycling site
    14,15,9,    # Residential areas?
    15,16,5,    # Industrial areas
]
alg_params = {
    'INPUT_RASTER':outputs['MosaicRasterLayersLandCoverND']['OUTPUT'],
    'RASTER_BAND':1,
    'TABLE':lutable,
    'NO_DATA':-9999,
    'RANGE_BOUNDARIES':0,
    'NODATA_FOR_MISSING':False,
    'DATA_TYPE':3,
    'OUTPUT': tempfolder + 'reclassLU.tif' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['ReclassifyValuesSimpleLandUse'] = processing.run("native:reclassifybytable", alg_params)


print('Raster calculator - combining LC and LU')
alg_params = {
    'BAND_A': 1,
    'BAND_B': 1,
    'BAND_C': None,
    'BAND_D': None,
    'BAND_E': None,
    'BAND_F': None,
    'EXTRA': '',
    'FORMULA': '(A + B) / 2',
    'INPUT_A': outputs['ReclassifyValuesSimpleLandUse']['OUTPUT'],
    'INPUT_B': outputs['ReclassifyValuesSimpleLandCover']['OUTPUT'],
    'INPUT_C': None,
    'INPUT_D': None,
    'INPUT_E': None,
    'INPUT_F': None,
    'NO_DATA': None,
    'OPTIONS': '',
    'RTYPE': 5,
    'OUTPUT': tempfolder + 'CombinedLCLU.tif'
}
outputs['RasterCalculatorLCLU'] = processing.run('gdal:rastercalculator', alg_params)



print('### WMCA OVIPOSITION and IUHD ###')
print('UHID: 0.1, LCLU: 0.9')
alg_params = {
    'BAND_A': 1,
    'BAND_B': 1,
    'BAND_C': None,
    'BAND_D': None,
    'BAND_E': None,
    'BAND_F': None,
    'EXTRA': '',
    'FORMULA': 'A * 0.9 + B * 0.1',
    'INPUT_A': outputs['RasterCalculatorLCLU']['OUTPUT'],
    'INPUT_B': outputs['ReclassifyValuesSimpleIUHD']['OUTPUT'],
    'INPUT_C': None,
    'INPUT_D': None,
    'INPUT_E': None,
    'INPUT_F': None,
    'NO_DATA': None,
    'OPTIONS': '',
    'RTYPE': 5,
    'OUTPUT': tempfolder + 'WMCA_ovi_iuhd.tif' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['WMCAOviposition'] = processing.run('gdal:rastercalculator', alg_params)

if useoldheatmaps == 0:
    print('Making ovi heatmap1')
    heatmap1 = heatmappart.heatmappart(outputs['WMCAOviposition']['OUTPUT'], 1, tempfolder, projwin)
    print('Making ovi heatmap2')
    heatmap2 = heatmappart.heatmappart(outputs['WMCAOviposition']['OUTPUT'], 2, tempfolder, projwin)
    print('Making ovi heatmap3')
    heatmap3 = heatmappart.heatmappart(outputs['WMCAOviposition']['OUTPUT'], 3, tempfolder, projwin)
    print('Making ovi heatmap4')
    heatmap4 = heatmappart.heatmappart(outputs['WMCAOviposition']['OUTPUT'], 4, tempfolder, projwin)
    print('Making ovi heatmap5')
    heatmap5 = heatmappart.heatmappart(outputs['WMCAOviposition']['OUTPUT'], 5, tempfolder, projwin)
    print('Making ovi heatmap6')
    heatmap6 = heatmappart.heatmappart(outputs['WMCAOviposition']['OUTPUT'], 6, tempfolder, projwin)
else:
    file_names = os.listdir(datafolder + 'tempheatmaps')
    
    for file_name in file_names:
        shutil.copy(os.path.join(datafolder + 'tempheatmaps/' + file_name), tempfolder + file_name)
    heatmap1 = datafolder + 'tempheatmaps/' + 'heatmap1.tif'
    heatmap2 = datafolder + 'tempheatmaps/' + 'heatmap2.tif'
    heatmap3 = datafolder + 'tempheatmaps/' + 'heatmap3.tif'
    heatmap4 = datafolder + 'tempheatmaps/' + 'heatmap4.tif'
    heatmap5 = datafolder + 'tempheatmaps/' + 'heatmap5.tif'
    heatmap6 = datafolder + 'tempheatmaps/' + 'heatmap6.tif'

print('Raster calculator (Combining heatmaps ovi)')
alg_params = {
    'BAND_A': 1,
    'BAND_B': 1,
    'BAND_C': 1,
    'BAND_D': 1,
    'BAND_E': 1,
    'BAND_F': 1,
    'EXTRA': '',
    'FORMULA': '(A + B + C + D + E + F) / 6',
    'INPUT_A': heatmap1,
    'INPUT_B': heatmap2,
    'INPUT_C': heatmap3,
    'INPUT_D': heatmap4,
    'INPUT_E': heatmap5,
    'INPUT_F': heatmap6,
    'NO_DATA': None,
    'OPTIONS': '',
    'RTYPE': 5,
    'OUTPUT': tempfolder + 'heatmap_ovi.tif' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['HeatmapWMCAOviposition'] = processing.run('gdal:rastercalculator', alg_params)


print('#### ADULT Model ####')

# Field calculator - Reclass LandCoverVector
alg_params = {
    'FIELD_LENGTH': 10,
    'FIELD_NAME': 'Reclassed',
    'FIELD_PRECISION': 3,
    'FIELD_TYPE': 1,
    'FORMULA': 'CASE WHEN \"DETALJTYP\" = \'ÖPMARK\' THEN 7 WHEN  \"DETALJTYP\" =  \'ÖPTORG\' THEN 4 WHEN  \"DETALJTYP\" = \'BEBHÖG\' THEN 2 WHEN \"DETALJTYP\" = \'BEBIND\' THEN 7 WHEN  \"DETALJTYP\" = \'BEBLÅG\'  THEN 5 WHEN  \"DETALJTYP\" = \'BEBSLUT\' THEN 1 WHEN  \"DETALJTYP\" = \'ODLÅKER\' THEN 7 WHEN  \"DETALJTYP\" = \'ODLFRUKT\' THEN 8 WHEN  \"DETALJTYP\" =   \'SKOGBARR\' THEN 8 WHEN  \"DETALJTYP\" =   \'SKOGLÖV\' THEN 9 WHEN  \"DETALJTYP\" = \'VATTEN\' THEN 0 END',
    'INPUT': outputs['ClipLandUse']['OUTPUT'],
    'OUTPUT': tempfolder + 'reclLUvector.shp' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['FieldCalculatorReclassLandcovervector'] = processing.run('native:fieldcalculator', alg_params)

# Urban Morphology: Morphometric Calculator (Grid) Building
alg_params = {
    'ATTR_TABLE': True,
    'FILE_PREFIX': 'Morph',
    'ID_FIELD': 'id',
    'IGNORE_NODATA': True,
    'INPUT_DEM': inDEM,
    'INPUT_DISTANCE': 200,
    'INPUT_DSM':inDSM,
    'INPUT_DSMBUILD': None,
    'INPUT_INTERVAL': 5,
    'INPUT_POLYGONLAYER':outputs['CreateGrid']['OUTPUT'],
    'OUTPUT_DIR': 'TEMPORARY_OUTPUT',
    'ROUGH': 0,  # Rule of thumb
    'SEARCH_METHOD': 0,  # Search throughout the grid extent (search distance not used)
    'USE_DSM_BUILD': False,
    'OUTPUT_DIR': QgsProcessing.TEMPORARY_OUTPUT
}
outputs['UrbanMorphologyMorphometricCalculatorGridBuilding'] = processing.run('umep:Urban Morphology: Morphometric Calculator (Grid)', alg_params)

# Field calculator
alg_params = {
    'FIELD_LENGTH': 10,
    'FIELD_NAME': 'FAIBuildDe',
    'FIELD_PRECISION': 3,
    'FIELD_TYPE': 0,
    'FORMULA': 'CASE WHEN  \"Morph_fai\" > 0.9 THEN 0.9 ELSE  \"Morph_fai\" END',
    'INPUT': outputs['CreateGrid']['OUTPUT'],
    'OUTPUT': tempfolder + 'faihigh.shp' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params)


print('Remove NoData LAI')
alg_params = { 
    'BAND' : 1, 
    'FILL_VALUE' : 0, 
    'INPUT' : outputs['ClipLAI']['OUTPUT'], 
    'OUTPUT' : QgsProcessing.TEMPORARY_OUTPUT  
}
outputs['ReclassifyValuesSingleRemoveNodataLai'] = processing.run("native:fillnodata", alg_params)


print('# Reclassify by table - NMDGrund') 
lctable = [
    1.9,2.1,6,# Open wetland
    2.9,3.1,4,# Arable land
    40.9,41.1,3,# Non-vegetated other open land
    41.9,42.1,5,# Vegetated other open land
    50.9,51.1,0, # Artificial surfaces, building
    51.9,52.1,0,# Artificial surfaces, not building or road/railway 
    52.9,53.1,0,# Road or railway.
    60.9,61.1,0, # Lakes or water-courses
    61.9,62.1,0,# Sea, ocean, estuaries or coastal lagoons.
    110.9,111.1,7, # Pine forest not on wetland
    111.9,112.1,7,# Spruce forest not on wetland
    112.9,113.1,7,# Mixed coniferous not on wetland
    113.9,114.1,7, # Mixed forest not on wetland?
    114.9,115.1,8,# 115 Deciduous forest not on wetland?
    115.9,116.1,8,# Deciduous hardwood forest not on wetland?
    116.9,117.1,8,  # Deciduous forest with deciduous hardwood forest not on wetland?
    117.9,118.1,5,  # Temporarily non-forest not on wetland
    120.9,121.1,8,# Pine forest on wetland
    121.9,122.1,8,    # Spruce forest on wetland
    122.9,123.1,8,  # Mixed coniferous on wetland
    123.9,124.1,8,    # Mixed forest on wetland
    124.9,125.1,10, # Deciduous forest on wetland
    125.9,126.1,10,# Deciduous hardwood forest on wetland
    126.9,127.1,10,# Deciduous forest with deciduous hardwood forest on wetland
    127.9,128.1,6,# Temporarily non-forest on wetland
]
alg_params = {
    'DATA_TYPE': 5,
    'INPUT_RASTER': outputs['ClipLandcover']['OUTPUT'],
    'NODATA_FOR_MISSING': False,
    'NO_DATA': -9999,
    'RANGE_BOUNDARIES': 0,
    'RASTER_BAND': 1,
    'TABLE': lctable,
    'OUTPUT': tempfolder + 'out_nmdgroundreclass.tif' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['ReclassifyByTableNmdgrund'] = processing.run('native:reclassifybytable', alg_params)


print('Rasterize (vector to raster) - LandCoverVector to Raster')
alg_params = {
    'BURN': 0,
    'DATA_TYPE': 5,
    'EXTENT': projwin,
    'EXTRA': '',
    'FIELD': 'Reclassed',
    'HEIGHT': 10,
    'INIT': None,
    'INPUT': outputs['FieldCalculatorReclassLandcovervector']['OUTPUT'],
    'INVERT': False,
    'NODATA': 0,
    'OPTIONS': '',
    'UNITS': 1,
    'WIDTH': 10,
    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
}
outputs['RasterizeVectorToRasterLandcovervectorToRaster'] = processing.run('gdal:rasterize', alg_params)


print('# Zonal statistics - DEM Mean')
alg_params = {
    'COLUMN_PREFIX': '_DEM',
    'INPUT': outputs['CreateGrid']['OUTPUT'], #outputs['UrbanMorphologyMorphometricCalculatorGridBuilding']['OUTPUT'], #parameters['MorphGrid'],
    'INPUT_RASTER': inDEM,
    'RASTER_BAND': 1,
    'STATISTICS': [2],
    'OUTPUT': tempfolder + 'zonstat.shp' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['ZonalStatisticsDemMean'] = processing.run('native:zonalstatisticsfb', alg_params)


print('Reclassify values (single) - Objekthojd0_5 - replaced with FillNoData')
alg_params = { 
    'BAND' : 1, 
    'FILL_VALUE' : 0, 
    'INPUT' : outputs['ClipHeight0to5']['OUTPUT'], 
    'OUTPUT' : QgsProcessing.TEMPORARY_OUTPUT  
}
outputs['ReclassifyValuesSingleObjekthojd0_5'] = processing.run("native:fillnodata", alg_params)


print('Field calculator - Wind Speed Topo')
alg_params = {
    'FIELD_LENGTH': 10,
    'FIELD_NAME': 'WSHeight', #too long?
    'FIELD_PRECISION': 3,
    'FIELD_TYPE': 0,
    'FORMULA': '2.6 * ( \"_DEMmean\" / 2) ^ 0.2',
    'INPUT': outputs['ZonalStatisticsDemMean']['OUTPUT'],
    'OUTPUT': tempfolder + 'windpower.shp' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['FieldCalculatorWindSpeedTopo'] = processing.run('native:fieldcalculator', alg_params)


print('# Rasterize (vector to raster) - FAIBUILD') 
alg_params = {
    'BURN': 0,
    'DATA_TYPE': 5,
    'EXTENT': projwin,
    'EXTRA': '',
    'FIELD': 'FAIBuildDe',
    'HEIGHT': 10,
    'INIT': None,
    'INPUT': outputs['FieldCalculator']['OUTPUT'],
    'INVERT': False,
    'NODATA': 0,
    'OPTIONS': '',
    'UNITS': 1,
    'WIDTH': 10,
    'OUTPUT': tempfolder + 'faibuild.tif' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['RasterizeVectorToRasterFaibuild'] = processing.run('gdal:rasterize', alg_params)


print('Urban Morphology: Morphometric Calculator (Grid) Vegetation')
alg_params = {
    'ATTR_TABLE': True,
    'FILE_PREFIX': 'Veg',
    'ID_FIELD': 'id',
    'IGNORE_NODATA': True,
    'INPUT_DEM': None,
    'INPUT_DISTANCE': 200,
    'INPUT_DSM': None,
    'INPUT_DSMBUILD': inCDSM, 
    'INPUT_INTERVAL': 5,
    'INPUT_POLYGONLAYER': outputs['CreateGrid']['OUTPUT'],
    'OUTPUT_DIR': 'TEMPORARY_OUTPUT',
    'ROUGH': 0,  # Rule of thumb
    'SEARCH_METHOD': 0,  # Search throughout the grid extent (search distance not used)
    'USE_DSM_BUILD': True,
    'OUTPUT_DIR': QgsProcessing.TEMPORARY_OUTPUT
}
outputs['UrbanMorphologyMorphometricCalculatorGridVegetation'] = processing.run('umep:Urban Morphology: Morphometric Calculator (Grid)', alg_params)

print('# Rasterize (vector to raster) - VegPAI')
alg_params = {
    'BURN': 0,
    'DATA_TYPE': 5,
    'EXTENT': projwin,
    'EXTRA': '',
    'FIELD': 'Veg_pai',
    'HEIGHT': 10,
    'INIT': None,
    'INPUT': outputs['CreateGrid']['OUTPUT'],
    'INVERT': False,
    'NODATA': None,
    'OPTIONS': '',
    'UNITS': 1,
    'WIDTH': 10,
    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
}
outputs['RasterizeVectorToRasterVegpai'] = processing.run('gdal:rasterize', alg_params)


print('Reclassify values (single) - Objekthojd5_45 - replaced with FillNoData')
alg_params = { 
    'BAND' : 1, 
    'FILL_VALUE' : 0, 
    'INPUT' : outputs['ClipHeight5to45']['OUTPUT'], 
    'OUTPUT' : QgsProcessing.TEMPORARY_OUTPUT  
}
outputs['ReclassifyValuesSingleObjekthojd5_45'] = processing.run("native:fillnodata", alg_params)

print('Reclassify by table - LAI ')
laitable = [
    0.0,0.05,1,
    0.05,0.5,4,
    0.5,1.0,5,
    1.0,1.5,6,
    1.5,2.0,7,
    2.0,2.5,8,
    2.5,3.0,9,
    3.0,100.0,10,
]
alg_params = {
    'DATA_TYPE': 5,
    'INPUT_RASTER': outputs['ReclassifyValuesSingleRemoveNodataLai']['OUTPUT'],
    'NODATA_FOR_MISSING': False,
    'NO_DATA': -9999,
    'RANGE_BOUNDARIES': 0,
    'RASTER_BAND': 1,
    'TABLE': laitable,
    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
}
outputs['ReclassifyByTableLai'] = processing.run('native:reclassifybytable', alg_params)


print('Reclassify by table - HeatMapHotspot')
costtable = [
    0,200,1,
    200,400,2,
    400,600,3,
    600,800,4,
    800,1000,5,
    1000,1200,6,
    1200,1400,7,
    1400,1600,8,
    1600,1800,9,
    1800,3000,10,
]
alg_params = {
    'DATA_TYPE': 5,
    'INPUT_RASTER': outputs['HeatmapWMCAOviposition']['OUTPUT'],
    'NODATA_FOR_MISSING': False,
    'NO_DATA': -9999,
    'RANGE_BOUNDARIES': 0,
    'RASTER_BAND': 1,
    'TABLE': costtable,
    'OUTPUT': tempfolder + 'out_heatmapreclassed.tif' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['ReclassifyByTableHeatmaphotspot'] = processing.run('native:reclassifybytable', alg_params)


print('Raster calculator - Get Vegetation from NMD')
alg_params = {
    'BAND_A': 1,
    'BAND_B': None, 'BAND_C': None, 'BAND_D': None, 'BAND_E': None, 'BAND_F': None,
    'EXTRA': '',
    'FORMULA': '((A == 2) + (A == 42) + (A == 111) + (A == 112) + (A == 113) + (A == 114) + (A == 115) + (A == 116) + (A == 117) + (A == 118) + (A == 121) + (A == 122) + (A == 123) + (A == 124) + (A == 125) + (A == 126) + (A == 127) + (A == 128))',
    'INPUT_A': outputs['ClipLandcover']['OUTPUT'],
    'INPUT_B':None, 'INPUT_C': None, 'INPUT_D': None, 'INPUT_E': None, 'INPUT_F': None,
    'NO_DATA': None,
    'OPTIONS': '',
    'RTYPE': 5,
    'OUTPUT': tempfolder + 'vegfromnmd.tif' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['RasterCalculatorGetVegetationFromNmd'] = processing.run('gdal:rastercalculator', alg_params)


print('Reclassify values (table) - Veg_Pai')
vegpaitable = [
    0.0,0.1,1,
    0.1,0.2,2,
    0.2,0.3,3,
    0.3,0.4,4,
    0.4,0.5,5,
    0.5,0.6,6,
    0.6,0.7,7,
    0.7,0.8,8,
    0.8,0.9,9,
    0.9,1.0,10,
]
alg_params = {
    'DATA_TYPE': 5,
    'INPUT_RASTER': outputs['RasterizeVectorToRasterVegpai']['OUTPUT'],
    'NODATA_FOR_MISSING': False,
    'NO_DATA': -9999,
    'RANGE_BOUNDARIES': 0,
    'RASTER_BAND': 1,
    'TABLE': vegpaitable,
    'OUTPUT': tempfolder + 'out_vegpaireclass.tif' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['ReclassifyValuesTableVeg_pai'] = processing.run('native:reclassifybytable', alg_params)


print('Rasterize (vector to raster) - FAIVEG')
alg_params = {
    'BURN': 0,
    'DATA_TYPE': 5,
    'EXTENT': projwin,
    'EXTRA': '',
    'FIELD': 'Veg_fai',
    'HEIGHT': 10,
    'INIT': None,
    'INPUT': outputs['CreateGrid']['OUTPUT'], # outputs['UrbanMorphologyMorphometricCalculatorGridVegetation']['OUTPUT'], #parameters['MorphGrid'],
    'INVERT': False,
    'NODATA': 0,
    'OPTIONS': '',
    'UNITS': 1,
    'WIDTH': 10,
    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
}
outputs['RasterizeVectorToRasterFaiveg'] = processing.run('gdal:rasterize', alg_params)


print('Rasterize (vector to raster) - Wind power law')
alg_params = {
    'BURN': 0,
    'DATA_TYPE': 5,
    'EXTENT': projwin,
    'EXTRA': '',
    'FIELD': 'WSHeight',
    'HEIGHT': 10,
    'INIT': None,
    'INPUT': outputs['FieldCalculatorWindSpeedTopo']['OUTPUT'],
    'INVERT': False,
    'NODATA': 0,
    'OPTIONS': '',
    'UNITS': 1,
    'WIDTH': 10,
    'OUTPUT': tempfolder + 'windpower.tif' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['RasterizeVectorToRasterWindPowerLaw'] = processing.run('gdal:rasterize', alg_params)


print('Reclassify values (single) - Remove NoData FAIBUILD (replaced with native FillNoData)')
alg_params = { 
    'BAND' : 1, 
    'FILL_VALUE' : 0, 
    'INPUT' : outputs['RasterizeVectorToRasterFaibuild']['OUTPUT'], 
    'OUTPUT' : QgsProcessing.TEMPORARY_OUTPUT  
}
outputs['ReclassifyValuesSingleRemoveNodataFaibuild'] = processing.run("native:fillnodata", alg_params)


print('Reclassify values (single) - LandCoverVectorRaster nodata to 0 (replaced with native FillNoData)')
alg_params = { 
    'BAND' : 1, 
    'FILL_VALUE' : 0, 
    'INPUT' : outputs['RasterizeVectorToRasterLandcovervectorToRaster']['OUTPUT'], 
    'OUTPUT' : tempfolder + 'out_landcoverreclass.tif' #QgsProcessing.TEMPORARY_OUTPUT  
}
outputs['ReclassifyValuesSingleLandcovervectorrasterNodataTo0'] = processing.run("native:fillnodata", alg_params)


print('Mosaic raster layers - Merge Heights')
#creating file list text file 
with open(tempfolder + 'mosaicHeight.txt', 'w') as file:
    file.write(str(Path(outputs['ReclassifyValuesSingleObjekthojd0_5']['OUTPUT'])))
    file.write('\n')
    file.write(str(Path(outputs['ReclassifyValuesSingleObjekthojd5_45']['OUTPUT'])))
    file.write('\n')
    file.close()

mosaicrasters(tempfolder + 'mosaicHeight.txt', tempfolder + 'mosaicHeight.tif')
outputs['MosaicRasterLayersMergeHeights'] = {'TARGET_OUT_GRID': tempfolder + 'mosaicHeight.tif'}

print('Reclassify by table - WindSpeedHeight')
windheighttable = [
    0.0,1.6482,10,
    1.6482,2.1574,9,
    2.1574,2.6666,8,
    2.6666,3.1758,7,
    3.1758,3.685,6,
    3.685,4.1942,5,
    4.1942,4.7034,4,
    4.7034,5.2126,3,
    5.2126,5.7218,2,
    5.7218,100.0,10,
]
alg_params = {
    'DATA_TYPE': 5,
    'INPUT_RASTER': outputs['RasterizeVectorToRasterWindPowerLaw']['OUTPUT'],
    'NODATA_FOR_MISSING': False,
    'NO_DATA': -9999,
    'RANGE_BOUNDARIES': 0,
    'RASTER_BAND': 1,
    'TABLE': windheighttable,
    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
}
outputs['ReclassifyByTableWindspeedheight'] = processing.run('native:reclassifybytable', alg_params)


print('Reclassify values (single) - Remove NoData FAIVEG (replaced with native FillNoData)')
alg_params = { 
    'BAND' : 1, 
    'FILL_VALUE' : 0, 
    'INPUT' : outputs['RasterizeVectorToRasterFaiveg']['OUTPUT'], 
    'OUTPUT' : QgsProcessing.TEMPORARY_OUTPUT  
}
outputs['ReclassifyValuesSingleRemoveNodataFaiveg'] = processing.run("native:fillnodata", alg_params)


nozerotable = [
    -10.0,0.1,1,
]

alg_params = {
    'DATA_TYPE': 5,
    'INPUT_RASTER': outputs['ReclassifyByTableLai']['OUTPUT'],
    'NODATA_FOR_MISSING': False,
    'NO_DATA': -9999,
    'RANGE_BOUNDARIES': 0,
    'RASTER_BAND': 1,
    'TABLE': nozerotable,
    'OUTPUT': tempfolder + 'out_laireclass.tif' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['ReclassifyValuesSingleReclass0To1Lai'] = processing.run('native:reclassifybytable', alg_params)


print('Raster calculator - Get Vegetation Heights')
alg_params = {
    'BAND_A': 1,
    'BAND_B': 1,
    'BAND_C': None,
    'BAND_D': None,
    'BAND_E': None,
    'BAND_F': None,
    'EXTRA': '',
    'FORMULA': 'A * B',
    'INPUT_A': outputs['RasterCalculatorGetVegetationFromNmd']['OUTPUT'],
    'INPUT_B': outputs['MosaicRasterLayersMergeHeights']['TARGET_OUT_GRID'],
    'INPUT_C': None,
    'INPUT_D': None,
    'INPUT_E': None,
    'INPUT_F': None,
    'NO_DATA': None,
    'OPTIONS': '',
    'RTYPE': 5,
    'OUTPUT': tempfolder + 'vegHeights.tif' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['RasterCalculatorGetVegetationHeights'] = processing.run('gdal:rastercalculator', alg_params)


print('Raster calculator - Ocean Distance in KM')
alg_params = {
    'BAND_A': 1,
    'BAND_B': None,
    'BAND_C': None,
    'BAND_D': None,
    'BAND_E': None,
    'BAND_F': None,
    'EXTRA': '',
    'FORMULA': 'A / 1000.0',
    'INPUT_A': outputs['ProximityRasterDistanceDistanceFromOcean']['OUTPUT'],
    'INPUT_B': None,
    'INPUT_C': None,
    'INPUT_D': None,
    'INPUT_E': None,
    'INPUT_F': None,
    'NO_DATA': None,
    'OPTIONS': '',
    'RTYPE': 5,
    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
}
outputs['RasterCalculatorOceanDistanceInKm'] = processing.run('gdal:rastercalculator', alg_params)


print('Reclassify by table - WindSpeedHeight')
vegheighttable = [
    0.0,5.0,10,
    5.0,10.0,9,
    10.0,20.0,8,
    20.0,30.0,7,
    30.0,100.0,6,
]
alg_params = {
    'DATA_TYPE': 5,
    'INPUT_RASTER': outputs['RasterCalculatorGetVegetationHeights']['OUTPUT'],
    'NODATA_FOR_MISSING': False,
    'NO_DATA': -9999,
    'RANGE_BOUNDARIES': 0,
    'RASTER_BAND': 1,
    'TABLE': vegheighttable,
    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
}
outputs['ReclassifyByTableVegheights'] = processing.run('native:reclassifybytable', alg_params)


print('Raster calculator - LAIFAICombo')
alg_params = {
    'BAND_A': 1,
    'BAND_B': 1,
    'BAND_C': 1,
    'BAND_D': None,'BAND_E': None,'BAND_F': None,
    'EXTRA': '',
    'FORMULA': '(((A * 0.6) * B) + C) / 2',
    'INPUT_A': outputs['ReclassifyValuesSingleReclass0To1Lai']['OUTPUT'],
    'INPUT_B': outputs['ReclassifyValuesSingleRemoveNodataFaiveg']['OUTPUT'],
    'INPUT_C': outputs['ReclassifyValuesSingleRemoveNodataFaibuild']['OUTPUT'],
    'INPUT_D': None,'INPUT_E': None,'INPUT_F': None,
    'NO_DATA': None,
    'OPTIONS': '',
    'RTYPE': 5,
    'OUTPUT': tempfolder + 'laifaicombo.tif' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['RasterCalculatorLaifaicombo'] = processing.run('gdal:rastercalculator', alg_params)


print('Reclassify values (single) - Reclass 0 to 1 - VegHeight')
nozerotable = [
    -10.0,0.1,1,
]
alg_params = {
    'DATA_TYPE': 5,
    'INPUT_RASTER': outputs['ReclassifyByTableVegheights']['OUTPUT'],
    'NODATA_FOR_MISSING': False,
    'NO_DATA': -9999,
    'RANGE_BOUNDARIES': 0,
    'RASTER_BAND': 1,
    'TABLE': nozerotable,
    'OUTPUT': tempfolder + 'out_vegheight.tif' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['ReclassifyValuesSingleReclass0To1Vegheight'] = processing.run('native:reclassifybytable', alg_params)


print('Raster calculator - WindReduxOcean')
alg_params = {
    'BAND_A': 1,
    'BAND_B': None,'BAND_C': None,'BAND_D': None,'BAND_E': None,'BAND_F': None,
    'EXTRA': '',
    'FORMULA': '(2.6 * 2.71828 ** (-0.015 * A))',
    'INPUT_A': outputs['RasterCalculatorOceanDistanceInKm']['OUTPUT'],
    'INPUT_B': None,'INPUT_C': None,'INPUT_D': None,'INPUT_E': None,'INPUT_F': None,
    'NO_DATA': None,
    'OPTIONS': '',
    'RTYPE': 5,
    'OUTPUT': tempfolder + 'winfreduc.tif' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['RasterCalculatorWindreduxocean'] = processing.run('gdal:rastercalculator', alg_params)


print('Reclassify by table - LAIFAI Ska bli output')
laifaitable = [
    0.0,0.05,1,
    0.05,0.5,4,
    0.5,1.0,5,
    1.0,1.5,6,
    1.5,2.0,7,
    2.0,2.5,8,
    2.5,3.0,9,
    3.0,100.0,10,
]
alg_params = {
    'DATA_TYPE': 5,
    'INPUT_RASTER': outputs['RasterCalculatorLaifaicombo']['OUTPUT'],
    'NODATA_FOR_MISSING': False,
    'NO_DATA': -9999,
    'RANGE_BOUNDARIES': 0,
    'RASTER_BAND': 1,
    'TABLE': laifaitable,
    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
}
outputs['ReclassifyByTableLaifaiSkaBliOutput'] = processing.run('native:reclassifybytable', alg_params)


print('Reclassify by table - Wind redux ocean')
windreduxoceantable = [
    -1.0,0.01,1, # added to include ocean greater than 30000
    0.01,1.82,10, 
    1.82,1.90,9,
    1.90,1.99,8,
    1.99,2.08,7,
    2.08,2.16,6,
    2.16,2.25,5,
    2.25,2.34,4,
    2.34,2.42,3,
    2.42,2.51,2,
    2.51,5.00,1,
]
alg_params = {
    'DATA_TYPE': 5,
    'INPUT_RASTER': outputs['RasterCalculatorWindreduxocean']['OUTPUT'],
    'NODATA_FOR_MISSING': False,
    'NO_DATA': -9999,
    'RANGE_BOUNDARIES': 0,
    'RASTER_BAND': 1,
    'TABLE': windreduxoceantable,
    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
}
outputs['ReclassifyByTableWindreduxocean'] = processing.run('native:reclassifybytable', alg_params)


print('Reclassify values (single) - Reclass 0 to 1 - LAIFAI')
nozerotable = [
    -10.0,0.1,1,
]
alg_params = {
    'DATA_TYPE': 5,
    'INPUT_RASTER': outputs['ReclassifyByTableLaifaiSkaBliOutput']['OUTPUT'],
    'NODATA_FOR_MISSING': False,
    'NO_DATA': -9999,
    'RANGE_BOUNDARIES': 0,
    'RASTER_BAND': 1,
    'TABLE': nozerotable,
    'OUTPUT': tempfolder + 'out_laifai.tif' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['ReclassifyValuesSingleReclass0To1Laifai'] = processing.run('native:reclassifybytable', alg_params)


print('Raster calculator - WindReduxOcean and height')
alg_params = {
    'BAND_A': 1,
    'BAND_B': 1,
    'BAND_C': None,'BAND_D': None,'BAND_E': None,'BAND_F': None,
    'EXTRA': '',
    'FORMULA': '(A + B) / 2',
    'INPUT_A': outputs['ReclassifyByTableWindspeedheight']['OUTPUT'],
    'INPUT_B': outputs['ReclassifyByTableWindreduxocean']['OUTPUT'],
    'INPUT_C': None,'INPUT_D': None,'INPUT_E': None,'INPUT_F': None,
    'NO_DATA': None,
    'OPTIONS': '',
    'RTYPE': 5,
    'OUTPUT': tempfolder + 'out_windreducheightocean.tif' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['RasterCalculatorCombineOceanHeightWind'] = processing.run('gdal:rastercalculator', alg_params)



print('### WMCA ADULT and HEATMAPOVI ###')
print('See Table 4 and 6 in Villes thesis')
alg_params = {
    'INPUT_A': outputs['ReclassifyValuesSingleReclass0To1Lai']['OUTPUT'], #LAI (Shade, moisture, wind reduction)
    'INPUT_B': outputs['ReclassifyByTableHeatmaphotspot']['OUTPUT'], #Heatmap (Oviposition hotspots)
    'INPUT_C': outputs['ReclassifyValuesSingleLandcovervectorrasterNodataTo0']['OUTPUT'], #Land use (Different urban land use)
    'INPUT_D': outputs['RasterCalculatorCombineOceanHeightWind']['OUTPUT'], #Ocean-altitude wind patterns (Large scale wind reduction)
    'INPUT_E': outputs['ReclassifyValuesTableVeg_pai']['OUTPUT'], #paiveg (Bird rich areas)
    'INPUT_F': outputs['ReclassifyValuesSingleReclass0To1Vegheight']['OUTPUT'], #Vegetation heights (Vegetation height suitability)
    'BAND_A': 1, 
    'BAND_B': 1, 
    'BAND_C': 1, 
    'BAND_D': 1, 
    'BAND_E': 1,
    'BAND_F': 1,
    'EXTRA': '',
    'FORMULA': 'A * 0.18 + B * 0.18 + C * 0.13 + D * 0.13 + E * 0.13 + F * 0.1',
    'NO_DATA': None,
    'OPTIONS': '',
    'RTYPE': 5,
    'OUTPUT': tempfolder + 'WMCA_adult1.tif' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['AdultsMCA1'] = processing.run('gdal:rastercalculator', alg_params)

alg_params = {
    'INPUT_A': outputs['ReclassifyValuesSingleReclass0To1Laifai']['OUTPUT'], #Merged LAI, faiveg, faibuild (Small scale wind reduction)
    'INPUT_B': outputs['ReclassifyByTableNmdgrund']['OUTPUT'] , #NMD Landcover (Land cover suitability)
    'INPUT_C': outputs['AdultsMCA1']['OUTPUT'], # from above
    'INPUT_D': None, 
    'INPUT_E': None, 
    'INPUT_F': None, 
    'BAND_A': 1, 
    'BAND_B': 1, 
    'BAND_C': 1, 
    'BAND_D': None, 
    'BAND_E': None,
    'BAND_F': None,
    'EXTRA': '',
    'FORMULA': 'A * 0.1 + B * 0.05 + C',
    'NO_DATA': None,
    'OPTIONS': '',
    'RTYPE': 5,
    'OUTPUT': tempfolder + 'WMCA_adult.tif' #QgsProcessing.TEMPORARY_OUTPUT
}
outputs['AdultsMCA2'] = processing.run('gdal:rastercalculator', alg_params)


shutil.copyfile(tempfolder + 'clipdsm.tif', outputfolder + 'clipdsm.tif')
shutil.copyfile(tempfolder + 'clipcdsm.tif', outputfolder + 'clipcdsm.tif')
shutil.copyfile(tempfolder + 'clipdem.tif', outputfolder + 'clipdem.tif')
shutil.copyfile(tempfolder + 'lai.tif', outputfolder + 'lai.tif')
shutil.copyfile(tempfolder + 'WMCA_adult.tif', outputfolder + 'WMCA_adult.tif')
shutil.copyfile(tempfolder + 'IUHD_final.tif', outputfolder + 'IUHD_final.tif')
shutil.copyfile(tempfolder + 'WMCA_ovi_iuhd.tif', outputfolder + 'WMCA_ovi_iuhd.tif')

end = time.time()
total_time = end - start
print('Script finished in ' + str(total_time / 60.) + ' minutes' )