# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------------
# LocalizationofCareServiceAreas.py
# Created by: Mark Pooley
# Description: This script takes DSAs below a user defined threshold and aggregates them to a neighboring DSA using visits occuring between the two
# and assigns to the best neighbor
# ---------------------------------------------------------------------------

# Import arcpy module
import arcpy
from arcpy import env
import numpy

# Local variables that should be loaded into ArcMap prior to running the script
#These will be changed to "get parameter as text" so the user can define what
#files to use.
OriginalSA = arcpy.GetParameterAsText(0)
DSA_Field = arcpy.GetParameterAsText(1)
LOC_Field = arcpy.GetParameterAsText(2)
DyadTable = arcpy.GetParameterAsText(3)
DSARec_Field = arcpy.GetParameterAsText(4)
DSAProv_Field = arcpy.GetParameterAsText(5)
VisitsDyad_Field = arcpy.GetParameterAsText(6)
Threshold = arcpy.GetParameterAsText(7)

IowaBorder = arcpy.GetParameterAsText(8)
ZCTAs = arcpy.GetParameterAsText(9)
OutputLocation = arcpy.GetParameterAsText(10)
CrosswalkOutput = arcpy.GetParameterAsText(11)
CrosswalkTable = arcpy.GetParameterAsText(12)
env.workspace = arcpy.GetParameterAsText(13)
OutputLocation = env.workspace
env.overwriteOutput = True

#Sort the initial dataset by LOC so DSAs will be appended to a list in ascending order
#of LOC. The cursor selects all DSAs with an LOC below the defined threshold value
arcpy.SetProgressor("step","Setting up data...",0,3,1)
OriginalSA = arcpy.Sort_management(OriginalSA,"Temp_shapeFileSorted",[[LOC_Field,"ASCENDING"]])

ThresholdString = float(Threshold) * 100
ThresholdString = str(int(ThresholdString))
#add DSA Revised field that will be used to reassign DSAs
arcpy.AddMessage("Creating 'DSA_Revised_" + str(ThresholdString) + "pct' field that will be used for reassignment.")
DSA_RevisedString = "DSA_Revised_" + str(ThresholdString) + "pct" #create a string for a field name generated from user defined threshold
arcpy.AddField_management(OriginalSA,DSA_RevisedString,"TEXT")

#Selection clause used to populate DSA_Revised field
whereClause_UpdateCursor = LOC_Field + ">" + str(Threshold)

OriginalSA_FieldList = [f.name for f in arcpy.ListFields(OriginalSA,"*")] #create a list of fields from the input file
arcpy.AddMessage("field list: " + str(OriginalSA_FieldList))

with arcpy.da.UpdateCursor(OriginalSA,OriginalSA_FieldList,whereClause_UpdateCursor) as DSA_updateCursor:
    arcpy.AddMessage("Populating DSA_Revised field with DSAs above the LOC: " + str(Threshold))
    for row in DSA_updateCursor:
        #Populate DSA_Revised field with DSAs that are above the user specified threshold
        row[OriginalSA_FieldList.index(DSA_RevisedString)] = row[OriginalSA_FieldList.index(DSA_Field)]
        DSA_updateCursor.updateRow(row)

DSARevised_Field = "DSA_Revised" # string variable to make selection clauses easier

arcpy.SetProgressorPosition(1)
arcpy.AddMessage("Finding DSAs in need of reassignment...")

#create a list of all the DSAs in need of reassignment
DSA_List = []

#cursor used to iterate through current list and create a list of DSAs in need of reassignment
with arcpy.da.SearchCursor(OriginalSA,DSA_Field,LOC_Field + ' < ' + str(Threshold)) as cursor:
    for row in cursor:
        DSA_List.append(row[0]) 
#temp list to append all the DSA's in need of reassignment to. This list isn't need, its'
arcpy.AddMessage(str(len(DSA_List)) + " DSAs are in need of reassignment.")

arcpy.SetProgressorPosition(2)
#Create a feature layer for the adjacent selection in the loop. I have no idea
#why this is needed, but for some reason the script fails when trying to select
#adjacent features on a "regular" shapefile.
FeatureLayer = arcpy.MakeFeatureLayer_management(OriginalSA,"Temporary_Layer")

AssignedDict ={} #create a dictionary that will house the DSAs that have been reassigned and what they've been reassigned to
DoubleCheckDict = {} #dicationary that will be used to contain DSA reassigned to another DSA that is in need of reassignment
DSA_Revised_List = []
Change_List = [] #list to append DSA that will need to be re-evaluated
arcpy.SetProgressorPosition(3)
arcpy.ResetProgressor()  

#list to track DSAs that have been removed
removeList = []

arcpy.SetProgressor("step","Reassiging DSAs",0,len(DSA_List),1)
#loop to reassign all the DSAs that are below the user specified threshold criteria
arcpy.AddMessage("Evaluating DSAs in need of reassignment...")
for i in range(0,len(DSA_List)):
    #creating object for status bar when running script
        
    currentDSA = DSA_List[i]
    arcpy.SetProgressorLabel(str(currentDSA) + " being evaluated...")
    
    #where clause for the current DSA in need of Reassignment to be used in later 
    #selections.
    whereClause ='"' + DSA_Field + " = "+ "'" + str(currentDSA) + "'" + '"'
    arcpy.AddMessage("current selection clause: " + str(whereClause))

    #create field list
    FieldList = [f.name for f in arcpy.ListFields(OriginalSA,"*")]
    arcpy.AddMessage("field list of original sa" + str(FieldList))
    
    with arcpy.da.SearchCursor(OriginalSA,FieldList,whereClause):
        for row in cursor:
            
            currentDSA_Patients_In = row[FieldList.index("Patients_In")]
            currentDSA_Patients_Total = row[FieldList.index("Patients_Total")]
    
    #DSA Rec Clause that will be used for selection in the DYAD Table later
    DSA_RecClause = DSARec_Field + " = " + currentDSA 

    #where clause that selects all attributes in future adjacent selection that aren't the current DSA in question
    whereNotClause = DSA_Field + " <> " + "'" + currentDSA + "'"
    
    #Select DSA that fits the iteration criteria of the loop and create a temporary
    #shapefile so adjacent features can be selected. This is a piece of intermediate data 
    #that will be overwritten throughout the loop
    selection = arcpy.Select_analysis(OriginalSA, "Temp_CurrentSelection", whereClause)
    
    #Select adjacent features with boundaries touching DSA in Question
    Adjacent_Selection = arcpy.SelectLayerByLocation_management(FeatureLayer,"BOUNDARY_TOUCHES",selection,"#","NEW_SELECTION")
    
    #create neighbor field list for use in cursor:
    NeighborField_List = [f.name for f in arcpy.ListFields(Adjacent_Selection, "8")]

    #create a temporary dictionary
    tempDict = {}

    #cursor to select the adjacent polygons that aren't the current Service Area
    Adjacent_DSA_List = []
    with arcpy.da.SearchCursor(Adjacent_Selection,NeighborField_List) as cursor:
        for row in cursor:
            nbrDSA = row[NeighborField_List.index("ZIP")]
            DyadLOC = float(currentDSA_Patients_In + row[NeighborField_List.index("Patients_In")]) / float(currentDSA_Patients_Total + row[NeighborField_List.index("Patients_Total")])
            tempDict[str(nbrDSA)] = DyadLOC
    
    #pull the DSA that maxmizes LOC with the current DSA in need of reassignment
    maxDSA = str((max(tempDict, key = tempDict.get)))

    #Check of Max DSA has been reassigned to another already
    if maxDSA in DSA_List:
        #reassign maxDSA to what the current maxDSA has already been reassigned to
        if maxDSA in AssignedDict.keys():
            maxDSA = AssignedDict[maxDSA] #re declare MaxDSA to be equal to what it was assigned to already. If max DSA in DSA List and that DSA has been reassigned, this will take care of that issue.
        else:
            #if the above isn't the case then the currentDSA will ned to be re-evaluated later 
            #create a dictionary of double checks that will be revisited at the end of the loop to take care of needed reassignments
            DoubleCheckDict[currentDSA] = maxDSA
            Change_List.append(currentDSA)
            
    #update the reassigned to field        
    with arcpy.da.UpdateCursor(OriginalSA,FieldList,whereClause) as cursor:
        for row in cursor:
            row[FieldList.index(DSA_RevisedString)] = maxDSA
    
    #Determine list length for loop in a bit
    ListLength = len(Adjacent_DSA_List)
    
    #add current DSA to Assigned Dictionary
    AssignedDict[currentDSA] = maxDSA



    arcpy.SetProgressorLabel(str(currentDSA) + " reassinged to " + str(maxDSA))
    arcpy.SetProgressorPosition()

arcpy.AddMessage("Checking for DSAs that were assigned to a Service Area that was later reassigned...")
"""
#For loop that will check for DSAs that were assigned to a DSA that was reassigned later and create a list of DSAs that need to be redone   
for key in DoubleCheckDict:
    if DoubleCheckDict[key] in AssignedDict:
        DoubleCheckDict[key] = AssignedDict[DoubleCheckDict[key]]
    else:
        pass
"""

arcpy.AddMessage("DSAs that need to be ammended: " + str(Change_List))
#Clear selections 
arcpy.SelectLayerByAttribute_management(FeatureLayer,"Clear_Selection")
arcpy.ResetProgressor()     

arcpy.SetProgressor("step","Checking for DSA assignment errors",0,len(Change_List),1)
arcpy.AddMessage("Checking for incorrect DSA assignment")
#For loop that checks for DSAs that were reassigned to DSAs that were later reassigned. 
for i in range(len(Change_List)):
    
    if Change_List[i] in AssignedDict:
        #Temp variable that is the correct DSA to assign to the one(s) in need of reassignment
        TempReassignVar = AssignedDict[Change_List[i]]
        arcpy.AddMessage(str(Change_List[i]) + " reassigned to: " + str(TempReassignVar))
        #where clause to select the DSAs that have a revised DSA matching that of the current iteration in the list
        DSARevised_whereClause = DSARevised_Field + ' = '+ "'" + str(Change_List[i]) + "'"
        
        #Select all the DSAs that are in need of assignment correction
        DSARevised_Reassign = arcpy.SelectLayerByAttribute_management(FeatureLayer,"NEW_SELECTION",DSARevised_whereClause)
        ReAssignedFieldList = [f.name for f in arcpy.ListFields(DSARevised_Reassign, "*")]
        #change the DSA revised field to the correct assignment
        with arcpy.da.UpdateCursor(DSARevised_Reassign,ReAssignedFieldList,DSARevised_whereClause) as cursor:
            for row in cursor:
                row[ReAssignedFieldList.index(DSA_RevisedString)] = TempReassignVar
                cursor.updateRow(row)
    arcpy.SetProgressorPosition()

arcpy.ResetProgressor()
#Clear selections to export the layer
arcpy.SelectLayerByAttribute_management(FeatureLayer,"Clear_Selection")

arcpy.AddMessage("Exporting feature layer to shapefile...")
#Save layer as a shapfile in a user defined location
copyFeatures = arcpy.CopyFeatures_management(FeatureLayer,"Temp_FeatureOutput","#","0","0","0") 

arcpy.AddMessage("Dissolving current DSA reassignment...")
#Dissolve output of DSA Reassignment. This is needed to 
TempDissolve = arcpy.Dissolve_management(copyFeatures,"Temp_Dissolve",DSARevised_Field,"#","MULTI_PART","DISSOLVE_LINES")


####################
#Island hunting part of the script
#This part looks for DSAs that are entirely bounded by another service area. DSAs on on the border of the state
#are removed from potential consideration. 
####################
"""
arcpy.AddMessage("Looking for island DSAs...")
#Get count of features for progressor tool
FeatureCount = int(arcpy.GetCount_management(TempDissolve).getOutput(0))

arcpy.SetProgressor("step","Determining what DSAs touch the state border...",0,2,1)

#add field to analysisl layer that will serve as an indicator of features touching the state boundary
arcpy.AddField_management(TempDissolve,"TOUCHES_BORDER","SHORT")
#Make a feature layer so selections can be done
FeatureLayer = arcpy.MakeFeatureLayer_management(TempDissolve,"DSAFeatureLayer")

#Select Features touching the State Border and change the "TOUCHES_BORDER" field to a 1 - indicating they touch the border
BorderSelection = arcpy.SelectLayerByLocation_management(FeatureLayer,"WITHIN_A_DISTANCE",IowaBorder,"1 Miles","NEW_SELECTION")
CandidateList = []
with arcpy.da.SearchCursor(BorderSelection,DSARevised_Field) as CandidateCursor:
    for row in CandidateCursor:
        CandidateList.append(str(row)[3:8])
CandiateListLength = len(CandidateList)

arcpy.AddMessage("Creating list of DSAs that don't touch the state boundary...")
arcpy.SetProgressorPosition()

#arcpy.SelectLayerByLocation_management("OutputFile_09052014_Dissolve","WITHIN_A_DISTANCE","Iowa_Boundary_Outline","1 Miles","NEW_SELECTION")
arcpy.CalculateField_management(BorderSelection,"TOUCHES_BORDER",1)
BorderSelection = arcpy.SelectLayerByLocation_management(FeatureLayer,"WITHIN_A_DISTANCE",IowaBorder,"1 miles","SWITCH_SELECTION")
arcpy.CalculateField_management(BorderSelection,"TOUCHES_BORDER",0)

DSAcursor = arcpy.da.SearchCursor(TempDissolve,DSARevised_Field,)
DSAList_Complete = []
for i in DSAcursor:
    DSAList_Complete.append(str(i)[3:8])

arcpy.AddMessage("Iterating through DSAs that don't touch the state border...")

arcpy.SetProgressorPosition()
arcpy.ResetProgressor()
IslandList = []
#create a dictionary of islands and the DSA they should be assigned to.
IslandDictionary = {}
arcpy.SetProgressor("step","Checking DSAs that don't touch the border...",0,len(DSAList_Complete),1)
#Loop that will evaluate all DSAs not touching a border to determine if they are an island
for i in range(len(DSAList_Complete)):
    
    currentDSA = DSAList_Complete[i]
    #arcpy.AddMessage("Current DSA: " + str(currentDSA))
    #where clause generated through each iteration of the loop
    whereClause =  DSARevised_Field + " = " + "'" + str(currentDSA) + "'"
    #arcpy.AddMessage("curent selection clause: " + whereClause)

    
    if currentDSA not in CandidateList:
        arcpy.SetProgressorLabel(str(currentDSA) + " does not touch boundary. Checking if DSA is an island")
                
        #clause that will later be used to create a cursor from all the features that aren't the current selection feature
        whereNotClause = DSARevised_Field + " <> " + "'" + str(currentDSA) + "'"

        #create a single selection that is temporary and checks
        selection = arcpy.Select_analysis(TempDissolve, "Temp_CurrentSelection", whereClause)
        #select features adjacent to the current selection
        Adjacent_Selection = arcpy.SelectLayerByLocation_management(FeatureLayer,"BOUNDARY_TOUCHES",selection,"#","NEW_SELECTION")

        #cursor to select items adjacent to the current selection
        Adjacent_cursor = arcpy.da.SearchCursor(Adjacent_Selection,DSARevised_Field, whereNotClause)
        

        TempList = [] #temp list for iterative process
        
    
        for i in Adjacent_cursor:
            TempList.append(str(i)[3:8]) #append the cleaned numbers (removes characters from the unicode string)

        
        # if the length of the temp list is only 1, that means the DSA has only one neighbor and is therefore an  island 
        if len(TempList) == 1:
            IslandList.append(currentDSA)
            IslandDictionary[currentDSA] = TempList[0]
            
            with arcpy.da.UpdateCursor(FeatureLayer,DSARevised_Field) as IslandCursor:
                for row in IslandCursor:
                    if row[0] == currentDSA:
                        
                        row = tuple([IslandDictionary[currentDSA]])
                        IslandCursor.updateRow(row)
        else:
            pass
        

    else:
        pass
    arcpy.SetProgressorPosition()


arcpy.AddMessage(str(len(IslandList)) +  " DSAs were found to be islands and reassigned.")

#Clear selections to export the layer
arcpy.SelectLayerByAttribute_management(FeatureLayer,"Clear_Selection")

#output feature layer to a feature class
copyFeatures = arcpy.CopyFeatures_management(FeatureLayer,"Temp_IslandOutput","#","0","0","0")

#dissolve the newly redifined service areas
arcpy.AddMessage("Dissolving into new service areas without islands...")
FinalOutput_Dissolve =  arcpy.Dissolve_management(copyFeatures,OutputName,DSARevised_Field,"#","MULTI_PART","DISSOLVE_LINES")

arcpy.AddMessage("Creating DSA to ZCTA crosswalk shapefile...")
DSA_ZCTA_Join = arcpy.SpatialJoin_analysis(ZCTAs,FinalOutput_Dissolve,CrosswalkOutput,"#","#","#","HAVE_THEIR_CENTER_IN","#","#")

#export ZCTA crosswalk table
arcpy.AddMessage("Exporting ZCTA Crosswalk to table...")
TempLayer = arcpy.MakeFeatureLayer_management(DSA_ZCTA_Join,"TempLayer")
arcpy.TableToTable_conversion(TempLayer,OutputLocation,"ZipCrosswalk_Table")

#ensure Excel output table has appropriate file extension
if ".xls" not in str(CrosswalkTable):
    CrosswalkTable = CrosswalkTable + ".xls"
arcpy.TableToExcel_conversion("ZipCrosswalk_Table", CrosswalkTable, "NAME","CODE")


#Delete Temporary files created during the processing
arcpy.AddMessage("Removing Temporary files...")
TempFeatures = arcpy.ListFeatureClasses()
TempList = []
for feature in TempFeatures:
    if "Temp" in feature:
        arcpy.Delete_management(feature)
        
"""
arcpy.AddMessage("DSA reassignment Complete!")

