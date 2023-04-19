
# Heatmap part model

from qgis.core import QgsProcessing
import processing

from processing.core.Processing import Processing
Processing.initialize()

def heatmappart(inRaster, value, tempfolder, projwin):
    
    output = {}

    if value == 6:
        formula = 'A >= ' + str(value)
    else:
        formula = 'logical_and( A < ' + str(value + 1) + ' , A >= ' + str(value) + ' )'

    # Raster calculator - Egg-Hotspots1
    alg_params = {
        'BAND_A': 1,
        'BAND_B': None,
        'BAND_C': None,
        'BAND_D': None,
        'BAND_E': None,
        'BAND_F': None,
        'EXTRA': '',
        'FORMULA': formula,
        'INPUT_A': inRaster,
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
    output['RasterCalculatorEgghotspots1'] = processing.run('gdal:rastercalculator', alg_params)
    
    # Raster pixels to points - HotspotPoints1
    alg_params = {
        'FIELD_NAME': 'VALUE',
        'INPUT_RASTER': output['RasterCalculatorEgghotspots1']['OUTPUT'],
        'RASTER_BAND': 1,
        'OUTPUT': tempfolder + 'heattemp' + str(value) + '.shp' #QgsProcessing.TEMPORARY_OUTPUT
    }
    output['RasterPixelsToPointsHotspotpoints1'] = processing.run('native:pixelstopoints', alg_params)

    # Extract by expression Hotspot1
    alg_params = {
        'EXPRESSION': 'VALUE = 1',
        'INPUT': output['RasterPixelsToPointsHotspotpoints1']['OUTPUT'],
        'OUTPUT': tempfolder + 'heatpoints' + str(value) + '.shp' #QgsProcessing.TEMPORARY_OUTPUT
    }
    output['ExtractByExpressionHotspot1'] = processing.run('native:extractbyexpression', alg_params)

    # Heatmap (Kernel Density Estimation) - Hotspot1
    alg_params = {
        'DECAY': 0,
        'INPUT': output['ExtractByExpressionHotspot1']['OUTPUT'],
        'KERNEL': 3,
        'OUTPUT_VALUE': 0,
        'PIXEL_SIZE': 10,
        'RADIUS': 400, # change from 500 in Ville thesis
        'RADIUS_FIELD': '',
        'WEIGHT_FIELD': '',
        'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
    }
    output['HeatmapKernelDensityEstimationHotspot1'] = processing.run('qgis:heatmapkerneldensityestimation', alg_params)


    # Raster calculator - Heatmap1
    formula = 'A  * ' + str(value)

    alg_params = { 
        'BAND_A' : 1, 
        'BAND_B' : None, 
        'BAND_C' : None, 
        'BAND_D' : None, 
        'BAND_E' : None, 
        'BAND_F' : None, 
        'EXTRA' : '', 
        'FORMULA' : formula, 
        'INPUT_A' : output['HeatmapKernelDensityEstimationHotspot1']['OUTPUT'], 
        'INPUT_B' : None, 
        'INPUT_C' : None, 
        'INPUT_D' : None, 
        'INPUT_E' : None, 
        'INPUT_F' : None, 
        'NO_DATA' : None, 
        'OPTIONS' : '', 
        'OUTPUT' : QgsProcessing.TEMPORARY_OUTPUT, 
        'PROJWIN' : None, 
        'RTYPE' : 5 
    }
    output['RasterCalculatorHeatmap1'] = processing.run("gdal:rastercalculator", alg_params)


    alg_params = {
        'INPUT':output['RasterCalculatorHeatmap1']['OUTPUT'],
        'BAND':1,
        'FILL_VALUE':0,
        'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
    }
    output['ReclassifyValuesSingleNodataTo0Heatmap1'] = processing.run("native:fillnodata", alg_params)

    # print('Warp (reproject) Testing All slopes to 10m res')
    alg_params = {
        'DATA_TYPE': 0,
        'EXTRA': '',
        'INPUT': output['ReclassifyValuesSingleNodataTo0Heatmap1']['OUTPUT'],
        'MULTITHREADING': False,
        'NODATA': None,
        'OPTIONS': '',
        'RESAMPLING': 0,
        'SOURCE_CRS': 'ProjectCrs',
        'TARGET_CRS': 'ProjectCrs',
        'TARGET_EXTENT': projwin,
        'TARGET_EXTENT_CRS': None,
        'TARGET_RESOLUTION': 10,
        'OUTPUT': tempfolder + 'heatmap' + str(value) + '.tif' #QgsProcessing.TEMPORARY_OUTPUT
    }
    output['Warpheatmap'] = processing.run('gdal:warpreproject', alg_params)


    return output['Warpheatmap']['OUTPUT']