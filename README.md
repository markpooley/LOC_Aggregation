LOC_Aggregation
===============

Aggregation of Service Areas falling below a user defined threshold of Localization of Care. 
Service Areas below threshold will be joined to neighbor according to visit data provided in a corresponding table.

Island checking (self explanatory), checks for Service Areas that are completely surrounded by another service Area and
adds them to the surroundign one. Prior to doing this, the script omits any service areas that touch the border of the 
analysis area (e.g. state border).

This isn't the most efficient script as it's one of the first I wrote (a while ago), but thought it woudl be good to post it in the event others are in need of as similar service
