# Import arcpy module
import arcpy
from arcpy import env
env.workspace = "C:\\Users\\mpooley\\Documents\\ArcGIS\\Projects\\Delta Dental\\Scratch.gdb"
env.overwriteOutput = True

# Local variables that should be loaded into ArcMap prior to running the script
#These will be changed to "get parameter as text" so the user can define what
#files to use.
OriginalSA = arcpy.GetParameterAsText(0)
Field = arcpy.GetParameterAsText(1)
IowaBorder = arcpy.GetParameterAsText(2)
FinalOutput = arcpy.GetParameterAsText(3)

FeatureCount = arcpy.GetCount_management(OriginalSA)
FeatureCount = int(FeatureCount.getOutput(0))

arcpy.SetProgressor("step","Determining what DSAs touch the state border...",0,2,1)

#add field to analysisl layer that will serve as an indicator of features touching the state boundary
arcpy.AddField_management(OriginalSA,"TOUCHES_BORDER","SHORT")
#Make a feature layer so selections can be done
FeatureLayer = arcpy.MakeFeatureLayer_management(OriginalSA,"DSAFeatureLayer")

#Select Features touching the State Border and change the "TOUCHES_BORDER" field to a 1 - indicating they touch the border
BorderSelection = arcpy.SelectLayerByLocation_management(FeatureLayer,"WITHIN_A_DISTANCE",IowaBorder,"1 miles","NEW_SELECTION")
CandidateList = []
with arcpy.da.SearchCursor(BorderSelection,Field) as CandidateCursor:
	for row in CandidateCursor:
		CandidateList.append(str(row)[3:8])
CandiateListLength = len(CandidateList)

arcpy.SetProgressorLabel("Creating list of DSAs that don't touch the state boundary...")
arcpy.SetProgressorPosition()

#arcpy.SelectLayerByLocation_management("OutputFile_09052014_Dissolve","WITHIN_A_DISTANCE","Iowa_Boundary_Outline","1 Miles","NEW_SELECTION")
arcpy.CalculateField_management(BorderSelection,"TOUCHES_BORDER",1)
BorderSelection = arcpy.SelectLayerByLocation_management(FeatureLayer,"WITHIN_A_DISTANCE",IowaBorder,"1 miles","SWITCH_SELECTION")
arcpy.CalculateField_management(BorderSelection,"TOUCHES_BORDER",0)

DSAcursor = arcpy.da.SearchCursor(OriginalSA,Field,)
DSAList_Complete = []
for i in DSAcursor:
	DSAList_Complete.append(str(i)[3:8])

arcpy.SetProgressorLabel("Iterating through DSAs that don't touch the state border")
arcpy.SetProgressorPosition()

IslandList = []
#create a dictionary of islands and the DSA they should be assigned to.
IslandDictionary = {}


for i in range(len(DSAList_Complete)):
	arcpy.SetProgressor("step","Checking DSAs that don't touch the border...",0,len(DSAList_Complete),1)
	currentDSA = DSAList_Complete[i]
	#arcpy.AddMessage("Current DSA: " + str(currentDSA))
	#where clause generated through each iteration of the loop
	whereClause =  Field + " = " + "'" + str(currentDSA) + "'"
	#arcpy.AddMessage("curent selection clause: " + whereClause)

	
	if currentDSA not in CandidateList:
		arcpy.SetProgressorLabel("DSA does not touch boundary. Checking if DSA is an island")
		
		#arcpy.AddMessage("Current DSA: " + str(currentDSA))

		#clause that will later be used to create a cursor from all the features that aren't the current selection feature
		whereNotClause = Field + " <> " + "'" + str(currentDSA) + "'"

		#create a single selection that is temporary and checks
		selection = arcpy.Select_analysis(OriginalSA, "CurrentSelection", whereClause)
		#select features adjacent to the current selection
		Adjacent_Selection = arcpy.SelectLayerByLocation_management(FeatureLayer,"BOUNDARY_TOUCHES",selection,"#","NEW_SELECTION")

		#cursor to select items adjacent to the current selection
		Adjacent_cursor = arcpy.da.SearchCursor(Adjacent_Selection,Field, whereNotClause)
		

		TempList = []
		#arcpy.SetProgressorPosition()
	
		for i in Adjacent_cursor:
			TempList.append(str(i)[3:8]) #append the cleaned numbers (removes characters from the unicode string)

		
        # if the length of the temp list is only 1, that means the DSA has only one neighbor and it likely to be an island 
		if len(TempList) == 1:
			IslandList.append(currentDSA)
			IslandDictionary[currentDSA] = TempList[0]
			arcpy.AddMessage("Deleting island DSA: " + str(currentDSA))
			with arcpy.da.UpdateCursor(FeatureLayer,Field) as IslandCursor:
				for row in IslandCursor:
					if row[0] == currentDSA:
						arcpy.AddMessage(IslandList[0] + " is being reassigned to " + str(row))
						row = tuple([IslandDictionary[currentDSA]])
						IslandCursor.updateRow(row)
		else:
			pass
		arcpy.SetProgressorPosition()

	else:
		#arcpy.AddMessage("DSA: "+ str(currentDSA) + " falls on a border")
		pass
	arcpy.SetProgressorPosition()


arcpy.AddMessage("List of island DSAs: " + str(IslandList))
arcpy.AddMessage("Dictionary of Island DSAs and where they should be assigned: "  + str(IslandDictionary))


#Clear selections to export the layer
arcpy.SelectLayerByAttribute_management(FeatureLayer,"Clear_Selection")

#output feature layer to a feature class
copyFeatures = arcpy.CopyFeatures_management(FeatureLayer,"IslandOutput","#","0","0","0")

#dissolve the newly redifined service areas
arcpy.AddMessage("Dissolving into new service areas without islands...")
arcpy.Dissolve_management(copyFeatures,FinalOutput,Field,"#","MULTI_PART","DISSOLVE_LINES")

