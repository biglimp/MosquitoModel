# MosquitoModel
A Weighted Multi-Criteria Analysis model for estimating mosquito prevalance in urban areas


This script (MyggmodelTRANSAFE_Uppsala.py) is based on the geograpgy master thesis from Ville Stålnacke at the Department of Earth Sciences, Univeristy of Gothenburg, 2021. The model is designed to be executed with available Swedish geodata and consist of four separate submodels plus an extract section defined by a model domain. 

The model is written in Python and exploits the PyQGIS API to prepare, manage, and reclassify the datasets that are used as inputs in the WMCA sections of the model.

An additional script (https://github.com/biglimp/LidarToDSMs) is availabe to create DSM, CDSM, LAI, land cover and DEM from NH Lidar data to be used in this model.

The model is set-up to work with open source Swedish national geodatasets data.

Third party QGIS plugins required:
QuickOSM
Processing for UMEP

